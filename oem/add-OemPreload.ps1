# Copyright (c) Microsoft Corporation and Contributors.

<#
.SYNOPSIS
    Provision a UUP Product with associated MSIX packages.

.DESCRIPTION
    Provision a UUP Product with associated MSIX packages.

.PARAMETER ImagePath
    [Offline] Specifies the path to the Windows image (e.g. G:\OfflineImage).

.Parameter KeepTempFiles
    Do not delete temporary files (for debug/troubleshooting scenarios).

.Parameter Online
    [Online] Modify the operating system that is currently running on the local computer.

.PARAMETER ProvisionPackagePath
    Specifies the location of packages to provision. This must be an absolute path.

.PARAMETER ProvisionPackagePathFilter
    Specifies the filespec to match

     The default is "*.msix". Thus if Q:\Packages\amd64 is a directory then

        -ProvisionPackagePath Q:\Packages\arm64

    is equivalent to

        -ProvisionPackagePath Q:\Packages\arm64\*.msix -ProvisionPackagePathFilter *.msix

.PARAMETER Permissive
    Be permissive. For example, registering a UUP product referencing a package that's not provisioned
    is a warning if -Permissive is specified (instead of an error when -Permissive is not specified).

.PARAMETER UupDefinitionPath
    Specifies the location of UUP Product definition files to provision. This must be an absolute path.

    This is a debugging/troubleshooting aid and not needed except as directed.

.PARAMETER UupDefinitionPathFilter
    Specifies the filespec to match

     The default is "*.xml". Thus if Q:\Packages\amd64 is a directory then

        -UupDefinitionPath Q:\Packages\arm64

    is equivalent to

        -UupDefinitionPath Q:\Packages\arm64\*.msix -UupDefinitionPathFilter *.xml

    This is a debugging/troubleshooting aid and not needed except as directed.

.PARAMETER CreateAppDataFolder
    Create the AppData folder when provisioning packages. This is/was a possible workaround for an issue creating model cache folders

.EXAMPLE
    Add-OemPreload -ImagePath G:\ -ProvisionPackagePath D:\ISO\Product\Contoso\arm64
#>

[CmdletBinding(SupportsShouldProcess=$true)]

Param(
    [Parameter(Mandatory=$true)]
    [string]$ImagePath,

    [switch]$KeepTempFiles,

    [switch]$Online,

    [Parameter(Mandatory=$true)]
    [string]$ProvisionPackagePath,

    [string]$ProvisionPackagePathFilter='*.msix',

    [switch]$Permissive,

    [string]$UupDefinitionPath,

    [string]$UupDefinitionPathFilter='*.xml',

    [switch]$CreateAppDataFolder
)

Set-StrictMode -Version 3.0

$ErrorActionPreference = "Stop"

if ($Online)
{
    Write-Host "ERROR: -Online not yet supported! Coming soon..." -ForegroundColor Red -BackgroundColor Black
    Exit 1
}

$start_now = Get-Date

$global:provisioned_packages_by_familyname = $null

function Get-TempFilename
{
    param(
        [string]$suffix
    )

    $when = $start_now.ToString("yyyymmdd-hhmm")
    if (([string]::IsNullOrEmpty($suffix)) -or ($suffix[0] -eq '.'))
    {
        return "Add-OemPreload-$when$suffix"
    }
    else
    {
        return "Add-OemPreload-$when-$suffix"
    }
}


function Mount-OfflineHive
{
    if (-not $Online)
    {
        Write-Host "Loading offline hive..."
        $hive = Join-Path $ImagePath 'Windows\System32\config\SOFTWARE'
        Write-Host "...Command: REG.EXE LOAD HKLM\appxprovisionpackage $hive"
        if ($WhatIfPreference -eq $false)
        {
            $error = REG.EXE LOAD HKLM\appxprovisionpackage $hive
            Test-RegExe $error
        }
        Write-Host "Loaded!"
    }
}

function Unmount-OfflineHive
{
    if ($Online)
    {
        return
    }

    if (Test-Path -Path Registry::HKLM\appxprovisionpackage)
    {
        [gc]::Collect()
        [gc]::WaitForPendingFinalizers()
        Write-Host ""
        Write-Host "Unloading offline hive..."
        Write-Host "...Command: REG.EXE UNLOAD HKLM\appxprovisionpackage"
        if ($WhatIfPreference -eq $false)
        {
            $error = REG.EXE UNLOAD HKLM\appxprovisionpackage
            Test-RegExe $error
        }
        Write-Host "Unloaded!"
    }
}

function Test-AbsolutePath
{
    param(
        [string]$path
    )

    if (-not ([System.IO.Path]::IsPathRooted($path)))
    {
        return $false
    }

    if (-not (Test-Path -Path $path))
    {
        return $false
    }

    $resolved = Resolve-Path $path
    if ($resolved -is [array])
    {
        # Resolve-Path returns list[2+] if it's wildcarded
        $resolved_path = Split-Path $path -Parent
    }
    else
    {
        $resolved_path = $path
    }
    if (-not (Test-Path -Path $resolved_path -Type Container))
    {
        return $false
    }

    return $true
}

function Get-IsAdmin
{
    return [Security.Principal.WindowsIdentity]::GetCurrent().Groups -contains 'S-1-5-32-544'
}

function Get-Plural
{
    param(
        [int]$count,
        [string]$singular,
        [string]$plural
    )

    if ($count -eq 1)
    {
        return $singular
    }

    if ([string]::IsNullOrEmpty($plural))
    {
        return $singular + 's'
    }
    else
    {
        return $plural
    }
}

function Get-TempPath
{
    return Join-Path $env:windir 'Temp'
}

function Remove-TempFile
{
    param(
        [string]$filename
    )

    if ($KeepTempFiles -eq $true)
    {
        Write-Host "...Keeping temporary file $filename"
    }
    else
    {
        Write-Host "...Removing temporary file $filename"
        if ($WhatIfPreference -eq $false)
        {
            if ($KeepTempFiles -eq $false)
            {
                Remove-Item -Path $filename -Force
            }
        }
    }
}

function Get-NameFromPackageFullName
{
    param(
        [string]$packageFullName
    )

    return ($packageFullName -split '_')[0]
}

function Get-ProductDefinition
{
    param(
        [string]$filename
    )

    # Expected schema
    # <UUP>
    #     <Product Id="...productid..." Version="...version...">
    #         <Packages>
    #              <Package PackageFullName="...packagefullname..."/>
    #              ...
    #         </Packages>
    #     </Product>
    # </UUP>

    $xml = [xml](Get-Content $filename -EA:Stop)
    if (($xml.SelectSingleNode('/UUP/Product[@Id]') -eq $null) -or ($xml.SelectSingleNode('/UUP/Product[@Version]') -eq $null))
    {
        Write-Host "ERROR: Invalid UUP Product definition file ($filename)" -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }
    $product_id = $xml.UUP.Product.Id
    $product_version = $xml.UUP.Product.Version
    $packages = $xml.SelectNodes('/UUP/Product/Packages/Package[@PackageFullName]')

    return $product_id, $product_version, $packages
}

function Get-ProductDefinitions
{
    param(
        [string]$path,
        [string]$filespec
    )

    if ([string]::IsNullOrEmpty($path))
    {
        $path = $ProvisionPackagePath
    }

    $uupdefinitions = Join-Path $path $filespec
    $files = Get-ChildItem -Path $uupdefinitions -Recurse
    if ($files -eq $null)
    {
        Write-Host "ERROR: No UUP Product definitions found ($uupdefinitions)" -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }

    ForEach ($f in $files)
    {
        Write-Host "...$f"
    }

    return $files
}

function Get-ProvisionedPackages
{
    if ($Online)
    {
        Write-Host "...Command: Get-AppxProvisionedPackage -Online"
        {
            return Get-AppxProvisionedPackage -Online
        }
    }
    else
    {
        Write-Host "...Command: Get-AppxProvisionedPackage -Path $ImagePath"
        if ($WhatIfPreference -eq $false)
        {
            return Get-AppxProvisionedPackage -Path $ImagePath
        }
    }
}

function Remove-ProvisionedPackages
{
    if ($Online)
    {
        Write-Host "ERROR: -Online not yet supported! Coming soon..." -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }

    # older iterations of this script [pre-October 2024] would provision packages
    # we've changed install model from provisioned [install for every user] to install once for LocalService.
    # current iteration of this script will convert provision packages to pinned, leaving no packages provisioned
    # We want to remove any model packages that are provisioned.
    $provisionedPackages = Get-ProvisionedPackages |? { $_.PackageName -like 'WindowsWorkload*' }
    if ($provisionedPackages -ne $null)
    {
        Write-Host ""
        Write-Host "Removing old provisioned Workload packages..."
    }
    foreach ($package in $provisionedPackages)
    {
        Write-Host "...Command: Remove-AppxProvisionedPackage -Path $ImagePath -PackageName $($package.PackageName)"
        if ($WhatIfPreference -eq $false)
        {
            Remove-AppxProvisionedPackage -Path $ImagePath -PackageName $package.PackageName
        }
    }
}

function Get-PackagesAssociatedWithUupProducts
{
    if ($Online)
    {
        Write-Host "ERROR: -Online not yet supported! Coming soon..." -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }
    else
    {
        Mount-OfflineHive
        $packages = @()
        $prefix = 'HKLM:\appxprovisionpackage'
        $uupproducts = Join-Path $prefix 'Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts'

        if (Test-Path -Path $uupproducts)
        {
            Get-ChildItem $uupproducts |% {
                $uupproduct = join-path $uupproducts $_.pschildName
                Get-ChildItem $uupproduct | % {
                    $packageFullName = $_.PSChildName
                    if ($packages.Contains($packageFullName) -eq $false)
                    {
                        $packages += $packageFullName
                    }
                }
            }
        }

        Unmount-OfflineHive
        return $packages
    }
}

function Convert-ProvisionedPackagesToFullNameHashtable
{
    param(
        $provisionedPackages
    )

    $hashtableByPackageFullName = [ordered]@{}
    ForEach ($app in $provisionedPackages)
    {
        $pi = Get-PackageIdentityFromPackageFullName $app.PackageName
        $hashtableByPackageFullName[$pi.PackageFullName] = $pi
    }
    return $hashtableByPackageFullName
}

function Add-PackagesToFullNameHashTable
{
    param(
        $packages,
        $hashtableByPackageFullName
    )

    ForEach ($package in $packages)
    {
        if ($hashtableByPackageFullName[$package] -eq $null)
        {
            $pi = Get-PackageIdentityFromPackageFullName $package
            $hashtableByPackageFullName[$pi.PackageFullName] = $pi
        }
    }
}

function Add-PackagesToFamilyNameHashTable
{
    param(
        $packages,
        $hashtableByFamilyName
    )

    ForEach ($package in $packages)
    {
        $pi = Get-PackageIdentityFromPackageFullName $package
        $hashtableByFamilyName[$pi.PackageFamilyName] = $pi.PackageFullName
    }
}

function PackageHasHigherVersionInHashTable
{
    param(
        $package,
        $provisioned_packages_by_familyname
    )

    $pi = Get-PackageIdentityFromPackageFullName $package

    $familyname = $pi.PackageFamilyName
    $version = $pi.Version
    $existing = $provisioned_packages_by_familyname[$familyname]
    if ($existing -eq $null)
    {
        return $false
    }

    $existing_pi = Get-PackageIdentityFromPackageFullName $existing
    $existing_version = $existing_pi.Version
    $version_fields = $version.split('.')
    $existing_version_fields = $existing_version.split('.')

    for ($i = 0; $i -lt 4; $i++)
    {
        $existing_field = [int]$existing_version_fields[$i]
        $field = [int]$version_fields[$i]
        if ($existing_field -gt $field)
        {
            return $true
        }
        if ($existing_field -lt $field)
        {
            return $false
        }
    }

    return $false
}

function Add-ApplicationKeysForPinnedPackages
{
    param(
        $packages
    )

    if ($Online)
    {
        Write-Host "ERROR: -Online not yet supported! Coming soon..." -ForegroundColor Red -BackgroundColor Black
        return
    }
    Mount-OfflineHive

    $prefix = 'HKLM\appxprovisionpackage'
    $applications = Join-Path $prefix 'Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Applications'
    foreach ($package in $packages)
    {
        $packageApplicationsPath = join-path $applications $package
        $packageSisPath = "C:\Program Files\Windowsapps\$package\appxmanifest.xml"

        Write-Host "...Command: REG.EXE ADD ""$packageApplicationsPath"" /v Path /t REG_SZ /d ""$packageSisPath"" /f"
        if ($WhatIfPreference -eq $false)
        {
            $error = REG.EXE ADD "$packageApplicationsPath"  /v Path /t REG_SZ /d "$packageSisPath" /f
            Test-RegExe $error
        }
    }

    Unmount-OfflineHive
}

function Remove-ApplicationKeysForPinnedPackages
{
    param(
        $packages
    )

    if ($Online)
    {
        Write-Host "ERROR: -Online not yet supported! Coming soon..." -ForegroundColor Red -BackgroundColor Black
        return
    }
    Mount-OfflineHive

    $prefix = 'HKLM\appxprovisionpackage'
    $psPrefix = 'HKLM:\appxprovisionpackage'
    $applications = Join-Path $prefix 'Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Applications'
    $psApplications = Join-Path $psPrefix 'Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Applications'
    foreach ($package in $packages)
    {
        $packageApplicationsPath = join-path $applications $package
        $psApplicationsPath = join-path $psApplications $package
        if (test-path -path $psApplicationsPath)
        {
            Write-Host "...Command: REG.EXE DELETE ""$packageApplicationsPath"" /f"
            if ($WhatIfPreference -eq $false)
            {
                $error = REG.EXE DELETE "$packageApplicationsPath" /f
                Test-RegExe $error
            }
        }
    }

    Unmount-OfflineHive
}

# MSIX Package filenames / identity mappings
#
# MSIX Filename        => {guid}_{version}_{architecture}.msix
# MSIX PackageFullName => {name}.1_{version}_{architecture}__8wekyb3d8bbwe
#
# Examples:
#   2cadfae3-6e06-3957-8e13-d6cc51eee9e6_0.3.245.0_arm64.msix = WindowsWorkload.NamedEntityRecognition.1_0.3.245.0_arm64__8wekyb3d8bbwe
#   2cadfae3-6e06-3957-8e13-d6cc51eee9e6_0.3.245.0_x64.msix   = WindowsWorkload.NamedEntityRecognition.1_0.3.245.0_x64__8wekyb3d8bbwe
#   ddf4cd9b-44e7-9485-5689-6df50be6c25a_0.3.245.0_arm64.msix = WindowsWorkload.TextRecognition.Qnn.1_0.3.245.0_arm64__8wekyb3d8bbwe
#
# The following mapping table is the list of all known Filename GUIDs to Package Names (minus the .1 suffix)
# It is required in offline deployment scenarios (WinPE lacks tar.exe)
# Keep the list fresh by running .\Get-PackageIdentityFromISO.ps1 <model ISO mount path>
#The following list is a *performance optimization* to avoid having to parse the MSIX file to get the package name
#Any package not in the following list will cause the MSIX file to be parsed to retrieve the package name
#The following list needs to be accurate against all ISOs a customer may reasonably execute against
$mappings_msix_filenameprefix_packagename = @{
    '007f35d1-db4e-842f-a821-e147d2fe1fe1' = 'WindowsWorkload.ScrRegDetection.Qnn.1'
    '14847cc3-88d4-0cbf-cfb7-1ab27f06eb15' = 'WindowsWorkload.TextRecognition.Lnl.1'
    '173dbfbf-9c9c-061e-91fa-c2db5a172435' = 'WindowsWorkload.PSTokenizer.Qnn.2.7'
    '1eb4c6ca-b288-3939-0c57-b8fa6bdfa6cb' = 'WindowsWorkload.PSOnnxRuntime.Stx.3.5'
    '1f2d37dc-379e-009f-9f6d-5a041e1d241d' = 'WindowsWorkload.LocalSkills.Stx.1'
    '21b6643b-bd3b-1589-52e6-87bbad309bf8' = 'WindowsWorkload.Data.SettingsModel.Qnn.1'
    '261f49bb-0eb4-dc23-df82-7080a02809b2' = 'WindowsWorkload.PSOnnxRuntime.3.2'
    '281c4dac-9ff5-dbb1-e969-89ee133bfd8a' = 'WindowsWorkload.PSTokenizerShared.Data.3.5'
    '286a7398-0eac-3629-7114-ea7fe87aeeb3' = 'WindowsWorkload.PSTokenizerShared.Stx.3.7'
    '2a0dfa69-2628-f2cd-4a78-f654af5e50c8' = 'WindowsWorkload.SemanticText.Stx.1'
    '30de3114-d1a7-aab6-a65f-ef5a746dbead' = 'WindowsWorkload.ImageSearch.Lnl.2'
    '3608320c-b0ef-35ca-215e-98625ea09023' = 'WindowsWorkload.Data.ImageSearch.Stx.1'
    '3b280eb3-0240-ab9f-ffbb-15a3b17483f5' = 'WindowsWorkload.QueryProcessor.Data.1'
    '4927b7e4-795f-1dda-92d7-143a9ca854c1' = 'WindowsWorkload.ImageTextSearch.Lnl.2'
    '4a312b26-b2bc-9c4f-697e-bd37bd38c298' = 'WindowsWorkload.QueryProcessor.Stx.1'
    '4a8123a9-5fd0-fc08-15a0-3889604df3d5' = 'WindowsWorkload.ImageTextSearch.Lnl.3'
    '4ae28bb8-ad1e-cdff-f422-16ff129697ae' = 'WindowsWorkload.LocalSkills.Qnn.1'
    '4b55cbc0-7149-a4db-1db3-eac245e266e9' = 'WindowsWorkload.Data.PhiSilica.J32.1'
    '4bd5f9fc-3d22-2319-ada2-a9e31722d66c' = 'WindowsWorkload.NamedEntityRecognition.Lnl.1'
    '500aef3f-e14c-4095-8256-cb0ac3f371f1' = 'WindowsWorkload.Data.ImageSearch.Lnl.1'
    '51645a2a-725b-fadc-49a9-9db46e4563ec' = 'WindowsWorkload.Manager.1'
    '52f04439-3938-152e-6809-ee5cfbc10993' = 'WindowsWorkload.LanguageModel.J32.1'
    '56a856b5-3d2e-fdcf-1fb2-cae85e519ede' = 'WindowsWorkload.Data.ContentExtraction.Qnn.1'
    '59782be5-5a3e-3a7d-b561-e48048e8b656' = 'WindowsWorkload.TopicProcessor.Stx.1'
    '5a4c95f6-4267-042e-5211-148ada7530cc' = 'WindowsWorkload.PSOnnxRuntime.Lnl.3.7'
    '5b3627bf-566c-6719-0cf2-6b1795d93aa9' = 'WindowsWorkload.TextRecognition.Stx.1'
    '5cce39b6-5186-6b7a-9831-d144ce02d98a' = 'WindowsWorkload.ImageSegmentation.1'
    '5dac85ea-de27-cb95-95eb-6375732a4c7c' = 'WindowsWorkload.LanguageModel.Data.J32.1'
    '5e12660e-44ab-8882-ebfe-f1250e9b7f90' = 'WindowsWorkload.ImageLLMAdapter.1'
    '5f315327-02fe-671b-f553-179b3508ae0b' = 'WindowsWorkload.PSOnnxRuntime.Stx.3.7'
    '60b9af26-38e4-b642-a74c-9dc974919c07' = 'WindowsWorkload.ImageTextSearch.Qnn.3'
    '61e42671-4c6d-a52a-2c7d-f786f5b2bc9c' = 'WindowsWorkload.PSTokenizer.Stx.2.7'
    '63a1bc26-1f6b-237d-9b4e-4b794dbfd050' = 'WindowsWorkload.Data.Analysis.Qnn.1'
    '6645a2ea-5804-a115-f379-7e4b27132a00' = 'WindowsWorkload.PSTokenizer.Lnl.2.7'
    '6880602f-c162-973c-3447-7bdff4d260a8' = 'WindowsWorkload.QueryProcessor.Qnn.1'
    '6cea2719-7a31-e388-6a4e-4d8620bf9180' = 'WindowsWorkload.TextContentModeration.1'
    '6d4627ba-8067-fee6-5254-069a8497461f' = 'WindowsWorkload.LanguageModel.Qnn.1'
    '6df9d3c2-cfda-e165-ece9-b88cf6d23797' = 'WindowsWorkload.Data.SettingsModel.Lnl.1'
    '6f5ba4de-b4b6-9253-aa28-c1a99434c514' = 'WindowsWorkload.Data.Analysis.Stx.1'
    '713c2cfe-5142-5016-07c6-be00da52d724' = 'WindowsWorkload.PSTokenizerShared.Qnn.3.7'
    '757343b6-fc34-cc9f-e913-527da308a51c' = 'WindowsWorkload.ImageScaler.1'
    '7b0d9694-6b7d-9587-48b3-59b76c09c7b4' = 'WindowsWorkload.ImageContentModeration.1'
    '7f26acc0-d169-1844-1b15-f330069e4df7' = 'WindowsWorkload.SemanticText.Data.1'
    '81054e32-601c-a517-c313-c9dea0eb6d6d' = 'WindowsWorkload.ImageSearch.Lnl.3'
    '81cdc518-a129-98a7-8a30-8e4a21859a9b' = 'WindowsWorkload.NamedEntityRecognition.Qnn.1'
    '83b489c3-f08a-fdc5-43a2-07d48a9affb2' = 'WindowsWorkload.PSTokenizer.2.7'
    '84bb8992-32ba-5bf3-e23e-8ca689a84ff5' = 'WindowsWorkload.PSOnnxRuntime.Qnn.3.7'
    '8602e0f0-4a88-6584-1faa-604fc7f19ba1' = 'WindowsWorkload.PSTokenizerShared.Lnl.3.5'
    '87e37cc0-3e5e-ff32-fd8e-c47978064684' = 'WindowsWorkload.ImageSearch.Stx.3'
    '87e95fc4-b66e-9f82-9a41-114531352494' = 'WindowsWorkload.SettingsModel.Data.1'
    '8bc0a1ab-339d-f7ac-373e-8d4007d1a53c' = 'WindowsWorkload.ImageSearch.Data.3'
    '8dffbc56-daef-85ee-c5c8-35e074817038' = 'WindowsWorkload.Parallax.1'
    '91c85e29-7596-a250-23da-d10c968374e4' = 'WindowsWorkload.QueryProcessor.Lnl.1'
    '92c9f6f5-d153-9326-9e9c-e8eb046c4fdb' = 'WindowsWorkload.ImageDescription.J32.1'
    '936c3353-afac-fd24-8b8d-c0e27b0211cc' = 'WindowsWorkload.ImageSearch.Qnn.2'
    '9959e792-3fa2-a9b6-db4b-607e9c36dec2' = 'WindowsWorkload.ImageTextSearch.Stx.2'
    '97bebc8f-c711-358e-1b39-bd7f2a3c8ed9' = 'WindowsWorkload.PSOnnxRuntime.Lnl.3.5'
    '99c8c976-ccf8-753b-683d-07c62b9e7e6c' = 'WindowsWorkload.ScrRegDetection.Lnl.1'
    '9e7b465c-64fb-61b1-3f2a-18348d91734a' = 'WindowsWorkload.ImageTextSearch.Qnn.2'
    '9fd35909-0e0b-702d-3552-7ae5e4d7ab39' = 'WindowsWorkload.PSTokenizerShared.Lnl.3.7'
    'a21d731f-299f-19d9-6ea2-53d0ed10823c' = 'WindowsWorkload.ScrRegDetection.Data.1'
    'a4ff6b05-edbf-9357-d49c-73f4861b0954' = 'WindowsWorkload.TopicProcessor.Lnl.1'
    'a5bf6d00-f878-966e-d2eb-22f8ea4b57db' = 'WindowsWorkload.TextContentModeration.Data.1'
    'a7d5832f-17ea-735d-fc9c-3558b64b909c' = 'WindowsWorkload.Data.ContentExtraction.Lnl.1'
    'a90ba0b9-af5d-2c57-0325-da4ba5e0b40c' = 'WindowsWorkload.SettingsModel.Stx.1'
    'abd41e2d-5f86-6aa4-ae41-cfcf82fe2b82' = 'WindowsWorkload.PSOnnxRuntime.Qnn.3.5'
    'b57e838b-9980-9010-005b-8a4f2fd3e92e' = 'WindowsWorkload.Host.1'
    'b5e13ce4-b08c-d623-a4ac-166e3b56f26d' = 'WindowsWorkload.Data.SettingsModel.Stx.1'
    'b6551a0a-0f16-038c-8714-a8bf42b939fa' = 'WindowsWorkload.PSOnnxRuntime.Lnl.3.7'
    'b6ae9bf6-fb4d-1e36-8ad8-3f2c288e6ae0' = 'WindowsWorkload.LocalSkills.Lnl.1'
    'bc8dfc28-22bf-7bba-001d-1bd953401d71' = 'WindowsWorkload.SemanticText.Lnl.1'
    'c15eb352-5ea9-1f86-c2cf-c672f144f202' = 'WindowsWorkload.Data.Analysis.Lnl.1'
    'c1aff73c-ebc3-a882-52f0-37f0b4be0239' = 'WindowsWorkload.SemanticText.Qnn.1'
    'c1bafd6d-b282-c474-5624-dcbfbe8b3339' = 'WindowsWorkload.PSTokenizerShared.Qnn.3.5'
    'c3ea969e-3d1d-004e-18b6-fa25dc6e5ab0' = 'WindowsWorkload.SessionManager.1'
    'c6a3c941-80b2-c959-d4bc-c79499d29816' = 'WindowsWorkload.ImageSearch.Stx.2'
    'cbafa2f6-4e6d-ea39-3e34-6b8c0964d650' = 'WindowsWorkload.ImageTextSearch.Stx.3'
    'ce7d85cb-492d-3491-4971-3ae7a6da453b' = 'WindowsWorkload.PSOnnxRuntime.Qnn.3.7'
    'd07a6f2a-64c5-5352-d1a3-25ff9292f67d' = 'WindowsWorkload.PSOnnxRuntime.Stx.3.7'
    'd8933cd4-e2bf-d7b8-caa9-0929c94e2de8' = 'WindowsWorkload.ScrRegDetection.Stx.1'
    'd9ec8c5a-39f0-144f-b1e2-88e8ee21aca3' = 'WindowsWorkload.PSTokenizerShared.Data.3.7'
    'dd5a5df2-12c5-7a1b-8356-72851999be3b' = 'WindowsWorkload.SettingsModel.Qnn.1'
    'ddf4cd9b-44e7-9485-5689-6df50be6c25a' = 'WindowsWorkload.TextRecognition.Qnn.1'
    'df5c1c14-7f7a-8d88-840a-fea4b5006809' = 'WindowsWorkload.TextContentModeration.Qnn.1'
    'e0a475d4-8eaf-9650-34d8-b784ce5e3b34' = 'WindowsWorkload.TopicProcessor.Qnn.1'
    'e17c707e-8fcb-106a-0079-2ecd8ab08634' = 'WindowsWorkload.NamedEntityRecognition.Stx.1'
    'e28da4dd-c4ea-371a-b8fa-3ac749d1bedd' = 'WindowsWorkload.QueryBlockList.1'
    'e7698967-f50f-bc74-c563-b65190a5f44b' = 'WindowsWorkload.ImageSearch.Qnn.3'
    'ef22dda4-6047-4e13-fc68-9249354fc9ab' = 'WindowsWorkload.ImageLLMAdapter.Data.1'
    'ef4ea2cb-0a7f-e531-1d14-4a70b505f6a5' = 'WindowsWorkload.Data.ContentExtraction.Stx.1'
    'f729f457-a8d0-1a74-eae1-cf4399157984' = 'WindowsWorkload.Data.ImageSearch.Qnn.1'
    'f816f1f5-7777-a502-79ff-82dd65bba2fb' = 'WindowsWorkload.SettingsModel.Lnl.1'
    'fd86af72-3103-2bad-4f2f-278be20ab5a7' = 'WindowsWorkload.PSTokenizerShared.Stx.3.5'
    'ff21267a-ccf0-b2e1-57e5-3acd786f0b8d' = 'WindowsWorkload.ImageTextSearch.Data.3'
    'ff43562a-1c67-b38a-6aad-93f7cd5881b2' = 'WindowsWorkload.ImageContentModeration.Data.1'
    'cd94cc2c-7099-d7c5-2fc8-82ed0777367a' = 'WindowsWorkload.ImageObjectExtractor.1'
    '10147743-e82d-620c-9923-2162de4a5a18' = 'WindowsWorkload.ImageObjectRemover.1'
}

function Get-PackageIdentityFromFilename
{
    param(
        [string]$filename
    )

    $fn = Split-Path $filename -Leaf
    $regex = '^(?<prefix>[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})_(?<version>\d+\.\d+\.\d+\.\d+)_(?<architecture>[A-Za-z0-9]+)\.msix$'
    if ($fn -Match $regex)
    {
        $prefix = $Matches.prefix
        $version = $Matches.version
        $architecture = $Matches.architecture

        $packageName = $mappings_msix_filenameprefix_packagename[$prefix]
        if ($packageName)
        {
            $version_fields = $version.Split('.')
            $resourceId = $null
            $publisherId = '8wekyb3d8bbwe'
            return [Windows.ApplicationModel.PackageIdentity]::FormatPackageFullName($packageName, [int]$version_fields[0], [int]$version_fields[1], [int]$version_fields[2], [int]$version_fields[3], $architecture, $resourceId, $publisherId)
        }
    }
    return $null
}

function Format-PackagePublisherId
{
    param(
        [string]$publisher
    )

    # Windows has no PackagePublisherIdFromPublisher
    # So we'll break our cardinal rule and parse package identity as strings

    # We'll use a dummy placeholder name but it must be at least PACKAGE_NAME_MIN_LENGTH (3)
    $packageFamilyName = [Windows.ApplicationModel.PackageIdentity]::FormatPackageFamilyNameFromNameAndPublisher("abc", $publisher)

    # PackageFamilyName = "abc_1234567890abc"
    # Ignore the leading name and underscore and voila! PublisherId
    return $packageFamilyName.Substring(4)
}

function Get-PackageIdentityFromMsix
{
    param(
        [string]$msix
    )

    $manifest = & tar.exe -xOf $msix AppxManifest.xml
    $xml = [xml]$manifest
    $identity = $xml.Package.Identity
    $fields = ($xml.Package.Identity | Select-Object Name,Version,ProcessorArchitecture,ResourceId,Publisher)
    $name = $fields.Name
    $version = $fields.Version
    $architecture = $fields.ProcessorArchitecture
    $resourceid = $fields.ResourceId
    $publisher = $fields.Publisher
    $publisherId = Format-PackagePublisherId $publisher
    $packageFamilyName = [Windows.ApplicationModel.PackageIdentity]::FormatPackageFamilyNameFromNameAndPublisherId($name, $publisherid)
    $version_fields = $version.split('.')
    $packageFullName = [Windows.ApplicationModel.PackageIdentity]::FormatPackageFullName($name, [int]$version_fields[0], [int]$version_fields[1], [int]$version_fields[2], [int]$version_fields[3], $architecture, $resourceid, $publisherid)
    $obj = [pscustomobject]@{
                Source = $msix
                Name = $name
                Version = $version
                Architecture = $architecture
                Resourceid = $resourceid
                Publisher = $publisher
                PublisherId = $publisherId
                PackageFamilyName = $packageFamilyName
                PackageFullName = $packageFullName
    }
    return $obj
}

function Get-PackageIdentityFromPackageFullName
{
    param(
        [string]$packageFullName
    )

    # Windows has no PackagePublisherIdFromPublisher
    # So we'll break our cardinal rule and parse package identity as strings
    $fields = $packageFullName.split('_')
    $name = $fields[0]
    $version = $fields[1]
    $architecture = $fields[2]
    $resourceId = $fields[3]
    $publisherId = $fields[4]
    $packageFamilyName = [Windows.ApplicationModel.PackageIdentity]::FormatPackageFamilyNameFromNameAndPublisherId($name, $publisherid)

    $obj = [pscustomobject]@{
                Source = $null
                Name = $name
                Version = $version
                Architecture = $architecture
                Resourceid = $resourceid
                Publisher = $null
                PublisherId = $publisherId
                PackageFamilyName = $packageFamilyName
                PackageFullName = $packageFullName
    }
    return $obj
}

function Provision-Packages
{
    if ([string]::IsNullOrEmpty($ProvisionPackagePath))
    {
        Write-Warning "...No packages to provision (-ProvisionPackagePath not specified)"
        return 0
    }
    $path = Join-Path $ProvisionPackagePath $ProvisionPackagePathFilter

    $packages = Get-ChildItem -Path $path -Recurse
    if ($packages -eq $null)
    {
        Write-Warning "...WARNING: No packages found ($path)"
        return 0
    }

    $provisioned_packages_by_packagefullname = [ordered]@{}
    $uup_associated_packages = Get-PackagesAssociatedWithUupProducts
    Add-PackagesToFullNameHashTable $uup_associated_packages $provisioned_packages_by_packagefullname

    # We can leverage Add-AppxProvisionedPackage's ability to update packages--but it requires the package to be provisioned.
    # The only difference between our pinned packages and provisioned is the Applications key--so add them back temporarily
    # All exits from this function should call Remove-ApplicationKeysForPinnedPackages to clear these keys
    Add-ApplicationKeysForPinnedPackages $uup_associated_packages

    $global:provisioned_packages_by_familyname = [ordered]@{}
    Add-PackagesToFamilyNameHashTable $uup_associated_packages $global:provisioned_packages_by_familyname

    $provisioned_packages = @()
    ForEach ($package in $packages)
    {
        # Is the package already provisioned?
        $packageIdentity_FullName = Get-PackageIdentityFromFilename $package
        if ($packageIdentity_FullName -eq $null)
        {
            $packageIdentity = Get-PackageIdentityFromMsix $package
            $packageIdentity_FullName = $packageIdentity.PackageFullName
        }
        if ($provisioned_packages_by_packagefullname[$packageIdentity_FullName] -ne $null)
        {
            Write-Host "...Skipping already provisioned package $($packageIdentity_FullName)"
            continue
        }

        # Is a higher version of the package already provisioned?
        if (PackageHasHigherVersionInHashTable $packageIdentity_FullName $provisioned_packages_by_familyname)
        {
            Write-Host "...Skipping package $($packageIdentity_FullName) because a higher version exists"
            continue
        }

        if ($Online)
        {
            Write-Host "...Command: Add-AppxProvisionedPackage -Online -PackagePath $package -SkipLicense -Regions ""all"" -ErrorAction:SilentlyContinue"
            if ($WhatIfPreference -eq $false)
            {
                $error = Add-AppxProvisionedPackage -Online -PackagePath $package -SkipLicense -Regions "all" -ErrorAction:SilentlyContinue
                $provisioned_packages += $packageIdentity_FullName
                Add-PackagesToFamilyNameHashTable $packageIdentity_FullName $provisioned_packages_by_familyname
            }
        }
        else
        {
            Write-Host "...Command: Add-AppxProvisionedPackage -Path $ImagePath -PackagePath $package -SkipLicense -Regions ""all"""
            if ($WhatIfPreference -eq $false)
            {
                $error = $null
                try
                {
                    $error = Add-AppxProvisionedPackage -Path $ImagePath -PackagePath $package -SkipLicense -Regions "all" -ErrorAction:SilentlyContinue
                    $provisioned_packages += $packageIdentity_FullName
                    Add-PackagesToFamilyNameHashTable $packageIdentity_FullName $provisioned_packages_by_familyname
                }
                catch
                {
                    Write-Host "ERROR: Provisioning package $package" -ForegroundColor Red -BackgroundColor Black
                    Write-Host ("" + $_).Trim() -ForegroundColor Red -BackgroundColor Black
                    Write-Host "See $($env:windir)\Logs\DISM\dism.log for more details" -ForegroundColor Red -BackgroundColor Black
                    Remove-ApplicationKeysForPinnedPackages $uup_associated_packages
                    Exit 1
                }
            }
        }
    }

    Remove-ApplicationKeysForPinnedPackages $uup_associated_packages

    return $provisioned_packages
}

function Convert-ProvisionedPackagesToPinned
{
    param(
        $provisionedPackages
    )

    if ($Online)
    {
        return
    }

    if ($provisionedPackages -eq $null -or $provisionedPackages.count -eq 0)
    {
        return
    }

    Mount-OfflineHive

    $provisionedPackageSet = @{}

    ForEach ($package in $provisionedPackages)
    {
        $provisionedPackageSet[$package] = $true
    }

    ForEach ($package in $provisionedPackageSet.Keys)
    {
        $prefix = 'HKLM\appxprovisionpackage'
        $psprefix = 'HKLM:\appxprovisionpackage'
        $applications = Join-Path $prefix 'Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Applications'
        $psApplications = Join-Path $psprefix 'Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Applications'
        $pinned = Join-Path $prefix 'Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Pinned'
        $pi = Get-PackageIdentityFromPackageFullName $package

        $packageApplicationsPath = join-path $applications $package
        $psPackageApplicationsPath = join-path $psApplications $package
        $packagePinnedPath = join-path $pinned $pi.packageFamilyName
        # We *just* provisioned this in Provision-Packages, so it should exist
        # the one legitimate case it doesn't exist is if multiple versions of the same package family were provisioned
        # only the latest version will have an ApplicationsPath. Pinned is family name and it doesn't hurt to just add the Pinned key.
        if (Test-Path -Path $psPackageApplicationsPath)
        {
            Write-Host "...Command: REG.EXE DELETE ""$packageApplicationsPath"" /f"
            if ($WhatIfPreference -eq $false)
            {
                $error = REG.EXE DELETE "$packageApplicationsPath" /f
                Test-RegExe $error
            }
        }

        Write-Host "...Command: REG.EXE ADD ""$packagePinnedPath"" /f"
        if ($WhatIfPreference -eq $false)
        {
            $error = REG.EXE ADD "$packagePinnedPath" /f
            Test-RegExe $error
        }
    }

    Unmount-OfflineHive
}

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

namespace Windows.ApplicationModel
{
    public class PackageIdentity
    {
        // http://msdn.microsoft.com/en-us/library/windows/desktop/hh446775(v=vs.85).aspx
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        internal struct PACKAGE_ID
        {
            public uint reserved;
            public uint processorAchitecture;

            // This following would normally be in PACKAGE_VERSION
            // We flatten it here to facilitate marshalling of this struct
            public ushort Version_Revision;
            public ushort Version_Build;
            public ushort Version_Minor;
            public ushort Version_Major;

            public String name;
            public String publisher;
            public String resourceId;
            public String publisherId;
        }

        [DllImport("userenv.dll", EntryPoint="DeriveAppContainerSidFromAppContainerName", ExactSpelling=true)]
        internal static extern int DeriveAppContainerSidFromAppContainerName(string packageFamilyName, out IntPtr psid);

        [DllImport("advapi32.dll", EntryPoint="GetLengthSid", ExactSpelling=true)]
        internal static extern uint GetLengthSid(IntPtr psid);

        [DllImport("advapi32.dll", EntryPoint="FreeSid", ExactSpelling=true)]
        internal static extern void FreeSid(IntPtr psid);

        [DllImport("Kernel32.dll")]
        internal static extern int PackageFamilyNameFromId(ref PACKAGE_ID packageId, ref uint packageFamilyNameLength, [MarshalAs(UnmanagedType.LPWStr)]StringBuilder packageFamilyName);

        [DllImport("Kernel32.dll")]
        internal static extern int PackageFullNameFromId(ref PACKAGE_ID packageId, ref uint packageFullNameLength, [MarshalAs(UnmanagedType.LPWStr)]StringBuilder packageFullName);

        internal static uint PACKAGE_FAMILY_NAME_MAX_LENGTH = 64;

        internal static uint PACKAGE_FULL_NAME_MAX_LENGTH = 127;

        internal const uint PROCESSOR_ARCHITECTURE_AMD64 = 9;           // x64
        internal const uint PROCESSOR_ARCHITECTURE_ARM = 5;
        internal const uint PROCESSOR_ARCHITECTURE_ARM64 = 12;
        internal const uint PROCESSOR_ARCHITECTURE_IA32_ON_ARM64 = 14;  // X86OnArm64
        internal const uint PROCESSOR_ARCHITECTURE_INTEL = 0;           // x86
        internal const uint PROCESSOR_ARCHITECTURE_NEUTRAL = 11;
        internal const uint PROCESSOR_ARCHITECTURE_UNKNOWN = 65535;

        public static string FormatArchitecture(uint architecture)
        {
            switch (architecture)
            {
                case PROCESSOR_ARCHITECTURE_AMD64:          { return "x64";        }
                case PROCESSOR_ARCHITECTURE_ARM:            { return "arm";        }
                case PROCESSOR_ARCHITECTURE_ARM64:          { return "arm64";      }
                case PROCESSOR_ARCHITECTURE_IA32_ON_ARM64:  { return "x86onArm64"; }
                case PROCESSOR_ARCHITECTURE_INTEL:          { return "x86";        }
                case PROCESSOR_ARCHITECTURE_NEUTRAL:        { return "";           }
                case PROCESSOR_ARCHITECTURE_UNKNOWN:        { return "?";          }
                default: { return null; }
            }
        }

        public static uint ParseArchitecture(string architecture)
        {
            if (string.IsNullOrEmpty(architecture))
            {
                return PROCESSOR_ARCHITECTURE_NEUTRAL;
            }
            else if (architecture.Equals("x64", StringComparison.OrdinalIgnoreCase))
            {
                return PROCESSOR_ARCHITECTURE_AMD64;
            }
            else if (architecture.Equals("arm", StringComparison.OrdinalIgnoreCase))
            {
                return PROCESSOR_ARCHITECTURE_ARM;
            }
            else if (architecture.Equals("arm64", StringComparison.OrdinalIgnoreCase))
            {
                return PROCESSOR_ARCHITECTURE_ARM64;
            }
            else if (architecture.Equals("x86onArm64", StringComparison.OrdinalIgnoreCase))
            {
                return PROCESSOR_ARCHITECTURE_IA32_ON_ARM64;
            }
            else if (architecture.Equals("x86", StringComparison.OrdinalIgnoreCase))
            {
                return PROCESSOR_ARCHITECTURE_INTEL;
            }
            else if (architecture.Equals("neutral", StringComparison.OrdinalIgnoreCase))
            {
                return PROCESSOR_ARCHITECTURE_NEUTRAL;
            }
            else
            {
                return PROCESSOR_ARCHITECTURE_UNKNOWN;
            }
        }

        public static string FormatPackageFamilyNameFromNameAndPublisher(string name, string publisher)
        {
            PACKAGE_ID packageId = new PACKAGE_ID();
            packageId.name = name;
            packageId.publisher = publisher;

            uint packageFamilyNameLength = PACKAGE_FAMILY_NAME_MAX_LENGTH + 1;
            StringBuilder packageFamilyName = new StringBuilder((int)packageFamilyNameLength);

            int rc = PackageFamilyNameFromId(ref packageId, ref packageFamilyNameLength, packageFamilyName);
            if (rc != 0)
            {
                Console.WriteLine(string.Format("ERROR: {0} (0x{0:X08}) in PackageFamilyNameFromId()", rc));
                System.Environment.Exit(rc);
            }
            return packageFamilyName.ToString();
        }

        public static string FormatPackageFamilyNameFromNameAndPublisherId(string name, string publisherId)
        {
            PACKAGE_ID packageId = new PACKAGE_ID();
            packageId.name = name;
            packageId.publisherId = publisherId;

            uint packageFamilyNameLength = PACKAGE_FAMILY_NAME_MAX_LENGTH + 1;
            StringBuilder packageFamilyName = new StringBuilder((int)packageFamilyNameLength);

            int rc = PackageFamilyNameFromId(ref packageId, ref packageFamilyNameLength, packageFamilyName);
            if (rc != 0)
            {
                Console.WriteLine(string.Format("ERROR: {0} (0x{0:X08}) in PackageFamilyNameFromId()", rc));
                System.Environment.Exit(rc);
            }
            return packageFamilyName.ToString();
        }

        public static string FormatPackageFullName(
            string name,
            ushort version_major, ushort version_minor, ushort version_build, ushort version_revision,
            string architecture, string resourceId, string publisherId)
        {
            uint processorArchitecture = ParseArchitecture(architecture);
            return FormatPackageFullName(name, version_major, version_minor, version_build, version_revision, processorArchitecture, resourceId, publisherId);
        }

        public static string FormatPackageFullName(
            string name,
            ushort version_major, ushort version_minor, ushort version_build, ushort version_revision,
            uint architecture, string resourceId, string publisherId)
        {
            PACKAGE_ID packageId = new PACKAGE_ID();
            packageId.name = name;
            packageId.Version_Major = version_major;
            packageId.Version_Minor = version_minor;
            packageId.Version_Build = version_build;
            packageId.Version_Revision = version_revision;
            packageId.processorAchitecture = architecture;
            packageId.resourceId = resourceId;
            packageId.publisherId = publisherId;

            uint packageFullNameLength = PACKAGE_FULL_NAME_MAX_LENGTH + 1;
            StringBuilder packageFullName = new StringBuilder((int)packageFullNameLength);

            int rc = PackageFullNameFromId(ref packageId, ref packageFullNameLength, packageFullName);
            if (rc != 0)
            {
                Console.WriteLine(string.Format("ERROR: {0} (0x{0:X08}) in PackageFullNameFromId()", rc));
                System.Environment.Exit(rc);
            }
            return packageFullName.ToString();
        }
    }
}
"@

function Add-PackageInformation
{
    param(
        [string]$filename,
        [string]$productid,
        [string]$productversion,
        $packages
    )

    if (($global:provisioned_packages_by_familyname -ne $null) -and ($global:provisioned_packages_by_familyname.Count -gt 0))
    {
        Write-Host '...Verifying package information'
        # NOTE: $global:msix_provisioned_packages isn't set because provisioned packages weren't enumerated because the image wasn't mounted in -WhatIf mode
        if ($WhatIfPreference -eq $false)
        {
            ForEach ($p in $packages)
            {
                $packageFullName = $p.PackageFullName
                $packageFamilyName = (Get-PackageIdentityFromPackageFullName $packageFullName).PackageFamilyName
                if ($global:provisioned_packages_by_familyname[$packageFamilyName] -eq $null)
                {
                    if ($Permissive)
                    {
                        Write-Warning "WARNING: $packageFullName in $filename is not provisioned"
                    }
                    else
                    {
                        Write-Host "ERROR: $packageFullName in $filename is not provisioned" -ForegroundColor Red -BackgroundColor Black
                        Exit 1
                    }
                }
            }
        }
    }

    Write-Host '...Adding package information'
    if ($Online -eq $false)
    {
        $prefix = 'HKLM\appxprovisionpackage'
        $psPrefix = 'HKLM:\appxprovisionpackage'
        $psuupProduct = Join-Path $psPrefix "Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts\$productid"
        $uupproduct = Join-Path $prefix "Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\UUPProducts\$productid"

        if (Test-Path -Path $psuupProduct)
        {
            Write-Host "...Removing previous product definition"
            Write-Host "...Command: REG.EXE DELETE ""$uupproduct"" /f"
            if ($WhatIfPreference -eq $false)
            {
                $error = REG.EXE DELETE "$uupproduct" /f
                Test-RegExe $error
            }
        }

        ForEach ($p in $packages)
        {
            $packageFullName = $p.PackageFullName
            $packageFamilyName = (Get-PackageIdentityFromPackageFullName $packageFullName).PackageFamilyName
            $packageFullName = $global:provisioned_packages_by_familyname[$packageFamilyName]
            $path = Join-Path $uupproduct $packageFullName
            Write-Host "...Adding package $packageFullName"
            Write-Host "...Command: REG.EXE ADD ""$path"" /f"
            if ($WhatIfPreference -eq $false)
            {
                $error = REG.EXE ADD "$path" /f
                Test-RegExe $error
            }

            if ($CreateAppDataFolder)
            {
                Ensure-AppDataFolderForPackage $packageFullName
            }
        }

        Write-Host "...Adding product version $productversion"
        Write-Host "...Command: REG.EXE ADD ""$uupproduct"" /v Version /t REG_SZ /d $productversion /f"
        Write-Host "...Command: REG.EXE ADD ""$uupproduct"" /v IsPinned /t REG_DWORD /d 1 /f"
        if ($WhatIfPreference -eq $false)
        {
            $error = REG.EXE ADD "$uupproduct" /v Version /t REG_SZ /d $productversion /f
            Test-RegExe $error

            $error = REG.EXE ADD "$uupproduct" /v IsPinned /t REG_DWORD /d 1 /f
            Test-RegExe $error
        }
    }

    return $packages.Count
}

function GrantLocalServiceAccess
{
    param(
        [string]$Path
    )
    $ACL = Get-Acl -Path $Path
    $Access = New-Object System.Security.AccessControl.FileSystemAccessRule("NT AUTHORITY\LOCAL SERVICE", "Modify, ListDirectory", "ContainerInherit, ObjectInherit", "None", "Allow")
    $ACL.SetAccessRule($Access)
    Set-Acl -Path $Path -AclObject $acl
}

function Ensure-AclsOnRoot
{
    param(
        [string]$Root
    )

    if (-not (test-path -path $Root))
    {
        Ensure-AclsOnRoot "$root\.."
        md $Root
    }

    $acl = get-acl -path $root
    if ($acl.owner -eq "BUILTIN\Administrators")
    {
        if ($acl.access | where { $_.IdentityReference -eq "BUILTIN\Administrators" -and $_.FileSystemRights -eq "Modify, Synchronize" -and $_.InheritanceFlags -eq "ContainerInherit, ObjectInherit" -and $_.AccessControlType -eq "Allow" })
        {
            return
        }
    }
    takeown /f $Root /a
    $ACL = Get-Acl -Path $Root
    $Access = New-Object System.Security.AccessControl.FileSystemAccessRule("BUILTIN\Administrators", "Modify, ListDirectory", "ContainerInherit, ObjectInherit", "None", "Allow")
    $ACL.SetAccessRule($Access)
    Set-Acl -Path $Root -AclObject $acl
}
function Ensure-AppDataFolderForPackage
{
    param(
        [string]$packageFullName
    )

    if ($Online -eq $false)
    {
        $pi = Get-PackageIdentityFromPackageFullName $packageFullName

        $appdataRoot = join-path $ImagePath "Programdata\Microsoft\Windows\AppRepository\Families"
        $appdataFolderForPackage = join-path $appdataRoot "ApplicationData\$($pi.packageFamilyName)\Machine"

        if (-not (test-path -path $appdataFolderForPackage))
        {
            Write-Host "...Creating folder $appdataFolderForPackage"
            Ensure-AclsOnRoot $appdataRoot
            md $appdataFolderForPackage
        }
        GrantLocalServiceAccess $appdataFolderForPackage
    }
}

function Set-ContentNoBomUtf8
{
    param(
        [string]$Path,
        [string]$Value,
        [switch]$Force
    )

    if ($Force -eq $true)
    {
        Set-Content ([Text.UTF8Encoding]::new().GetBytes($Value)) -Encoding Byte -PSPath $Path -Force
    }
    else
    {
        Set-Content ([Text.UTF8Encoding]::new().GetBytes($Value)) -Encoding Byte -PSPath $Path
    }
}

function Test-RegExe
{
    param(
        [string]$result
    )

    if ([string]::IsNullOrEmpty($result))
    {
        Write-Host "ERROR: No success message" -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }
    if ($result -Match 'ERROR:')
    {
        Write-Host $error -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }
    if ($result -NotMatch 'The operation completed successfully')
    {
        Write-Host "$result" -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }
}

# ----------------------------------------------------------------------
# Aaaaand we're off to the races! (i.e. Main)

if (($Online -eq $false) -and ([string]::IsNullOrEmpty($ImagePath)))
{
    Write-Host "ERROR: -ImagePath <path> is required for offline mode" -ForegroundColor Red -BackgroundColor Black
    Exit 1
}

$registry_hive_software = Join-Path $ImagePath 'Windows\System32\config\SOFTWARE'
if (($Online -eq $false) -and -not(Test-Path -Path $registry_hive_software -PathType Leaf))
{
    Write-Host "ERROR: -ImagePath <path> is required for offline mode (E.g. -ImagePath G:\OfflineImage)" -ForegroundColor Red -BackgroundColor Black
    Exit 1
}

if (-not ([string]::IsNullOrEmpty($ProvisionPackagePath)))
{
    if (-not (Test-AbsolutePath $ProvisionPackagePath))
    {
        Write-Host "ERROR: -ProvisionPackagePath must be an absolute path (e.g. Q:\Packages\arm64)" -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }
}

if ([string]::IsNullOrEmpty($UupDefinitionPath))
{
    if ([string]::IsNullOrEmpty($ProvisionPackagePath))
    {
        Write-Host "ERROR: -UupDefinitionPath or -ProvisionPackagePath must be defined" -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }
}
else
{
    if (-not (Test-AbsolutePath $UupDefinitionPath))
    {
        Write-Host "ERROR: -UupDefinitionPath must be an absolute path (e.g. Q:\Packages\arm64)" -ForegroundColor Red -BackgroundColor Black
        Exit 1
    }
}

$isadmin = Get-IsAdmin
if ($isadmin -eq $false)
{
    Write-Host "Access Denied. Run from an admin prompt" -ForegroundColor Red -BackgroundColor Black
    Exit 1
}

if ($WhatIfPreference -eq $true)
{
    Write-Host "-WhatIf enabled. No changes will be made to the system"
}

Unmount-OfflineHive
try {
    Write-Host ""
    Write-Host "Enumerating UUP Product definition files..."
    $uupfiles = Get-ProductDefinitions $UupDefinitionPath $UupDefinitionPathFilter
    $uupfiles_count = ($uupfiles | Measure-Object).Count
    $word_products = Get-Plural $uupfiles_count 'Product'
    Write-Host "Enumerated $uupfiles_count UUP $word_products!"

    Remove-ProvisionedPackages

    Write-Host ""
    Write-Host "Provisioning packages..."
    $provisioned_packages = Provision-Packages
    $provisioned_count = 0
    if ($provisioned_packages -ne $null)
    {
        $provisioned_count = $provisioned_packages.Count
    }
    $word_packages = Get-Plural $provisioned_count 'Package'

    Convert-ProvisionedPackagesToPinned $provisioned_packages
    Write-Host "Provisioned $provisioned_count $word_packages!"

    Write-Host ""
    $word_products = Get-Plural $uupfiles_count 'Product'
    Write-Host "Processing $uupfiles_count UUP $($word_products)..."

    Mount-OfflineHive

    $packages_count = 0
    ForEach ($uupproductfile in $uupfiles)
    {
        Write-Host ""
        Write-Host "Loading $uupproductfile..."
        $product_id, $product_version, $packages = Get-ProductDefinition $uupproductfile
        Write-Host "...Loaded: $product_id version $product_version ($($packages.Count) packages)"

        Write-Host ""
        Write-Host "Adding product and package information: $product_id version $product_version..."
        $packages_added = Add-PackageInformation $uupproductfile $product_id $product_version $packages
        $packages_count = $packages_count + $packages.count
        Write-Host "Added!"
    }
}
finally {
    Unmount-OfflineHive
}

Write-Host ""
Write-Host "Summary:"
$word_packages = Get-Plural $provisioned_count 'Package'
Write-Host "    Provisioned $provisioned_count MSIX $word_Packages"
$word_products = Get-Plural $uupfiles_count 'Product'
$word_packages = Get-Plural $packages_count 'Package'
Write-Host "    Registered $uupfiles_count UUP $word_products with $packages_count MSIX $word_packages"
