#include <windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <cstdio>
#include <string>
#include <algorithm>
#include <climits>
#pragma comment(lib,"mfplat.lib")
#pragma comment(lib,"mf.lib")
#pragma comment(lib,"mfreadwrite.lib")
#pragma comment(lib,"mfuuid.lib")
#pragma comment(lib,"ole32.lib")
template<class T>void Release(T*& p){if(p){p->Release();p=nullptr;}}
static HRESULT MakeWriter(PCWSTR path,IMFMediaType* input,IMFSinkWriter** writer,DWORD* stream){
    IMFMediaType* output=nullptr;HRESULT hr=MFCreateMediaType(&output);
    if(SUCCEEDED(hr))hr=output->SetGUID(MF_MT_MAJOR_TYPE,MFMediaType_Video);
    if(SUCCEEDED(hr))hr=output->SetGUID(MF_MT_SUBTYPE,MFVideoFormat_H264);
    if(SUCCEEDED(hr))hr=output->SetUINT32(MF_MT_AVG_BITRATE,4000000);
    if(SUCCEEDED(hr))hr=output->SetUINT32(MF_MT_INTERLACE_MODE,MFVideoInterlace_Progressive);
    for(const GUID* key:{&MF_MT_FRAME_SIZE,&MF_MT_FRAME_RATE,&MF_MT_PIXEL_ASPECT_RATIO}){
        UINT64 value=0;if(SUCCEEDED(hr)&&SUCCEEDED(input->GetUINT64(*key,&value)))hr=output->SetUINT64(*key,value);
    }
    if(SUCCEEDED(hr))hr=MFCreateSinkWriterFromURL(path,nullptr,nullptr,writer);
    if(SUCCEEDED(hr))hr=(*writer)->AddStream(output,stream);
    if(SUCCEEDED(hr))hr=(*writer)->SetInputMediaType(*stream,input,nullptr);
    if(SUCCEEDED(hr))hr=(*writer)->BeginWriting();Release(output);return hr;
}
int wmain(int argc,wchar_t** argv){
    unsigned seconds=5;std::wstring output,match=L"vid_1bcf&pid_2d03";
    for(int i=1;i<argc;i++){
        if(!wcscmp(argv[i],L"--seconds")&&i+1<argc)seconds=wcstoul(argv[++i],nullptr,10);
        else if(!wcscmp(argv[i],L"--output")&&i+1<argc)output=argv[++i];
        else if(!wcscmp(argv[i],L"--match")&&i+1<argc)match=argv[++i];else return 2;
    }
    if(seconds<5||seconds>30)return 2;std::transform(match.begin(),match.end(),match.begin(),towlower);
    CoInitializeEx(nullptr,COINIT_MULTITHREADED);HRESULT hr=MFStartup(MF_VERSION);
    IMFAttributes* attrs=nullptr;IMFActivate** devices=nullptr;UINT32 count=0;
    if(SUCCEEDED(hr))hr=MFCreateAttributes(&attrs,1);
    if(SUCCEEDED(hr))hr=attrs->SetGUID(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID);
    if(SUCCEEDED(hr))hr=MFEnumDeviceSources(attrs,&devices,&count);
    bool found=false,passed=false;
    for(UINT32 i=0;i<count;i++){
        WCHAR* link=nullptr;devices[i]->GetAllocatedString(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK,&link,nullptr);
        std::wstring name=link?link:L"";CoTaskMemFree(link);std::transform(name.begin(),name.end(),name.begin(),towlower);
        if(found||name.find(match)==std::wstring::npos)continue;found=true;
        IMFMediaSource* source=nullptr;IMFSourceReader* reader=nullptr;IMFMediaType* type=nullptr;IMFSinkWriter* writer=nullptr;DWORD writerStream=0;
        hr=devices[i]->ActivateObject(IID_PPV_ARGS(&source));printf("ActivateObject=0x%08X\n",(unsigned)hr);fflush(stdout);
        if(SUCCEEDED(hr))hr=MFCreateSourceReaderFromMediaSource(source,nullptr,&reader);
        if(SUCCEEDED(hr))hr=reader->GetCurrentMediaType(static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM),&type);
        UINT32 width=0,height=0,rate=0,denom=0;GUID subtype={};
        if(type){MFGetAttributeSize(type,MF_MT_FRAME_SIZE,&width,&height);MFGetAttributeRatio(type,MF_MT_FRAME_RATE,&rate,&denom);type->GetGUID(MF_MT_SUBTYPE,&subtype);}
        printf("format=%ux%u rate=%u/%u subtype=%08lX\n",width,height,rate,denom,subtype.Data1);
        if(SUCCEEDED(hr)&&!output.empty()){hr=MakeWriter(output.c_str(),type,&writer,&writerStream);printf("writer=0x%08X\n",(unsigned)hr);}
        unsigned frames=0,ticks=0,discontinuities=0;unsigned long long totalBytes=0;LONGLONG first=LLONG_MIN,last=0,maxGap=0;ULONGLONG firstWall=0;
        const ULONGLONG deadline=GetTickCount64()+seconds*1000+8000;
        while(SUCCEEDED(hr)&&GetTickCount64()<deadline){
            IMFSample* sample=nullptr;DWORD actual=0,flags=0;LONGLONG timestamp=0;
            hr=reader->ReadSample(static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM),0,&actual,&flags,&timestamp,&sample);
            if(FAILED(hr)||(flags&(MF_SOURCE_READERF_ERROR|MF_SOURCE_READERF_ENDOFSTREAM))){Release(sample);if(SUCCEEDED(hr))hr=E_FAIL;break;}
            if(flags&MF_SOURCE_READERF_STREAMTICK)ticks++;
            DWORD bytes=0;if(sample)sample->GetTotalLength(&bytes);
            if(sample&&bytes){
                if(first==LLONG_MIN){first=timestamp;firstWall=GetTickCount64();}
                else {if(timestamp<=last)discontinuities++;maxGap=std::max(maxGap,timestamp-last);}
                last=timestamp;frames++;totalBytes+=bytes;
                if(writer){sample->SetSampleTime(timestamp-first);LONGLONG duration=0;if(FAILED(sample->GetSampleDuration(&duration))&&rate)sample->SetSampleDuration(10000000LL*denom/rate);hr=writer->WriteSample(writerStream,sample);}
            }
            Release(sample);
            if(first!=LLONG_MIN&&last-first>=10000000LL*seconds&&GetTickCount64()-firstWall>=seconds*1000)break;
        }
        const ULONGLONG wall=first==LLONG_MIN?0:GetTickCount64()-firstWall;const LONGLONG span=first==LLONG_MIN?0:last-first;
        if(writer){HRESULT finalHr=writer->Finalize();printf("Finalize=0x%08X\n",(unsigned)finalHr);if(SUCCEEDED(hr))hr=finalHr;}
        passed=SUCCEEDED(hr)&&frames>=seconds*5&&span>=10000000LL*seconds&&wall>=seconds*1000&&discontinuities==0&&maxGap<=10000000;
        printf("RESULT hr=0x%08X passed=%d frames=%u bytes=%llu stream_ticks=%u video_ms=%lld wall_ms=%llu max_gap_ms=%lld timestamp_errors=%u\n",(unsigned)hr,passed,frames,totalBytes,ticks,span/10000,wall,maxGap/10000,discontinuities);fflush(stdout);
        Release(writer);Release(type);Release(reader);if(source){source->Shutdown();Release(source);}devices[i]->ShutdownObject();
    }
    for(UINT32 i=0;i<count;i++)devices[i]->Release();CoTaskMemFree(devices);Release(attrs);MFShutdown();CoUninitialize();
    if(!found)printf("No matching camera found.\n");return passed?0:1;
}
