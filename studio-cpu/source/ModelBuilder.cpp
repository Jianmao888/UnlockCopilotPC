#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define UNICODE
#include <windows.h>
#include <openvino/openvino.hpp>
#include <openvino/core/preprocess/pre_post_process.hpp>
#include <fstream>
#include <vector>
#include <string>
#include <cstdio>
#include <cstring>
#include <cmath>
static std::string Utf8(const std::wstring& value){int n=WideCharToMultiByte(CP_UTF8,0,value.data(),(int)value.size(),nullptr,0,nullptr,nullptr);std::string s(n,'\0');WideCharToMultiByte(CP_UTF8,0,value.data(),(int)value.size(),s.data(),n,nullptr,nullptr);return s;}
static std::vector<unsigned char> Resource(HMODULE module,int id){HRSRC resource=FindResourceW(module,MAKEINTRESOURCEW(id),RT_RCDATA);if(!resource)throw std::runtime_error("Resource missing");DWORD size=SizeofResource(module,resource);HGLOBAL loaded=LoadResource(module,resource);auto p=static_cast<const unsigned char*>(LockResource(loaded));if(!p)throw std::runtime_error("Resource cannot be read");std::vector<unsigned char> data(p,p+size);const char* key="DROWSSAP";for(size_t i=0;i<data.size();i++)data[i]^=(unsigned char)key[i%8];return data;}
static ov::Output<ov::Node> FindTensor(const std::shared_ptr<ov::Model>& model,const std::string& name){for(auto& node:model->get_ordered_ops())for(size_t i=0;i<node->get_output_size();i++)if(node->output(i).get_names().count(name))return node->output(i);throw std::runtime_error("Required intermediate tensor absent: "+name);}
int wmain(int argc,wchar_t** argv){
 if(argc!=4){fprintf(stderr,"Usage: ModelBuilder.exe legacy-resource.dll output-directory cpu-runtime-directory\n");return 2;}
 HMODULE resources=LoadLibraryExW(argv[1],nullptr,LOAD_LIBRARY_AS_DATAFILE|LOAD_LIBRARY_AS_IMAGE_RESOURCE);if(!resources){fprintf(stderr,"Resource load failed: %lu\n",GetLastError());return 1;}
 try{
  const std::wstring output=argv[2],runtime=argv[3];ov::Core core;core.register_plugin(Utf8(runtime+L"\\openvino_intel_cpu_plugin.dll"),"CPU");
  struct Entry{int id;const char* label;const char* input;const char* first;const char* second;};
  const Entry entries[]={{101,"face101","image:0","compress_v1/Conv2d_13_pointwiseANDConv/Conv_4/BiasAdd:0",nullptr},{109,"matting109","normed_rgbm:0","PostProcess/stage0/x0.5/seg:0","PostProcess/stage0/x1/seg:0"},{113,"pose113","imageBatch:0","Detector/Conv16/BiasAdd:0","Detector/logitsP:0"},{132,"light132","input_3:0","tf.math.tanh",nullptr}};
  for(const auto& e:entries){
   auto xml=Resource(resources,e.id),weights=Resource(resources,e.id+1);std::string text(xml.begin(),xml.end());ov::Tensor weightTensor(ov::element::u8,ov::Shape{weights.size()},weights.data());auto model=core.read_model(text,weightTensor);
   if(e.id==113)model=std::make_shared<ov::Model>(ov::OutputVector{FindTensor(model,"Detector/Conv16/BiasAdd:0"),FindTensor(model,"Detector/logitsP:0")},model->get_parameters(),"StudioPoseCPU");
   ov::preprocess::PrePostProcessor pp(model);pp.input().tensor().set_layout(ov::Layout("NHWC"));pp.input().model().set_layout(ov::Layout("NCHW"));pp.output(0).model().set_layout(ov::Layout("NCHW"));pp.output(0).tensor().set_layout(ov::Layout("NHWC"));
   if(e.id==109){pp.output(1).model().set_layout(ov::Layout("NCHW"));pp.output(1).tensor().set_layout(ov::Layout("NHWC"));}
   model=pp.build();model->input().get_tensor().set_names({e.input});model->output(0).get_tensor().set_names({e.first});if(e.second)model->output(1).get_tensor().set_names({e.second});
   auto compiled=core.compile_model(model,"CPU",{ov::hint::performance_mode(ov::hint::PerformanceMode::LATENCY)});auto request=compiled.create_infer_request();
   for(size_t i=0;i<compiled.inputs().size();i++){ov::Tensor input(compiled.input(i).get_element_type(),compiled.input(i).get_shape());memset(input.data(),0,input.get_byte_size());request.set_input_tensor(i,input);}
   for(int n=0;n<3;n++)request.infer();
   for(size_t i=0;i<compiled.outputs().size();i++){auto result=request.get_output_tensor(i);if(result.get_element_type()!=ov::element::f32)throw std::runtime_error("Unexpected output type");auto values=result.data<float>();for(size_t j=0;j<result.get_size();j++)if(!std::isfinite(values[j]))throw std::runtime_error("Non-finite inference output");}
   std::wstring label;for(const char* p=e.label;*p;p++)label+=(wchar_t)*p;std::ofstream stream(output+L"\\"+label+L"-cpu.blob",std::ios::binary);compiled.export_model(stream);if(!stream.good())throw std::runtime_error("Blob write failed");printf("model=%s cpu_inference=passed\n",e.label);fflush(stdout);
  }
  FreeLibrary(resources);return 0;
 }catch(const std::exception& e){fprintf(stderr,"Model preparation failed: %s\n",e.what());FreeLibrary(resources);return 1;}
}
