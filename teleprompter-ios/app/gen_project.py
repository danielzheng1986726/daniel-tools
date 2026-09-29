#!/usr/bin/env python3
"""生成最小 Xcode 工程（不依赖 xcodegen）。改了源文件列表就重跑一次。"""
import os, glob
NAME="Prompter"; BUNDLE="com.example.prompter"; DISPLAY="提词"
srcs=sorted(os.path.basename(p) for p in glob.glob("Sources/*.swift"))
def oid(n): return "%024X" % n
ids={k: oid(i+1) for i,k in enumerate(["proj","target","maingroup","srcgroup","prodgroup","app","sources","frameworks","resources","cfg_proj","cfg_proj_debug","cfg_proj_release","cfg_tgt","cfg_tgt_debug","cfg_tgt_release"])}
for i,s in enumerate(srcs): ids["ref_"+s]=oid(100+i); ids["bf_"+s]=oid(200+i)
tgt=f"""
				CODE_SIGN_STYLE = Automatic;
				CURRENT_PROJECT_VERSION = 1;
				GENERATE_INFOPLIST_FILE = YES;
				INFOPLIST_FILE = Info.plist;
				INFOPLIST_KEY_CFBundleDisplayName = "{DISPLAY}";
				INFOPLIST_KEY_NSCameraUsageDescription = "录口播";
				INFOPLIST_KEY_NSMicrophoneUsageDescription = "录口播的声音，并用本机识别跟读翻页";
				INFOPLIST_KEY_NSSpeechRecognitionUsageDescription = "本机识别你念到哪一句，用来翻页";
				INFOPLIST_KEY_NSPhotoLibraryAddUsageDescription = "把录好的视频存进相册";
				INFOPLIST_KEY_LSSupportsOpeningDocumentsInPlace = YES;
				INFOPLIST_KEY_UIApplicationSupportsIndirectInputEvents = YES;
				INFOPLIST_KEY_UILaunchScreen_Generation = YES;
				INFOPLIST_KEY_UISupportedInterfaceOrientations = UIInterfaceOrientationPortrait;
				INFOPLIST_KEY_UIUserInterfaceStyle = Dark;
				IPHONEOS_DEPLOYMENT_TARGET = 26.0;
				LD_RUNPATH_SEARCH_PATHS = "$(inherited) @executable_path/Frameworks";
				MARKETING_VERSION = 0.1;
				PRODUCT_BUNDLE_IDENTIFIER = {BUNDLE};
				PRODUCT_NAME = "$(TARGET_NAME)";
				SWIFT_EMIT_LOC_STRINGS = YES;
				SWIFT_VERSION = 5.0;
				TARGETED_DEVICE_FAMILY = 1;
"""
prj="""
				ALWAYS_SEARCH_USER_PATHS = NO;
				CLANG_ENABLE_MODULES = YES;
				CLANG_ENABLE_OBJC_ARC = YES;
				ENABLE_USER_SCRIPT_SANDBOXING = YES;
				SDKROOT = iphoneos;
				SWIFT_STRICT_CONCURRENCY = minimal;
"""
o="// !$*UTF8*$!\n{\n\tarchiveVersion = 1;\n\tclasses = {\n\t};\n\tobjectVersion = 77;\n\tobjects = {\n"
for s in srcs: o+=f"\t\t{ids['bf_'+s]} = {{isa = PBXBuildFile; fileRef = {ids['ref_'+s]}; }};\n"
for s in srcs: o+=f"\t\t{ids['ref_'+s]} = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = {s}; sourceTree = \"<group>\"; }};\n"
o+=f"\t\t{ids['app']} = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = {NAME}.app; sourceTree = BUILT_PRODUCTS_DIR; }};\n"
o+=f"\t\t{ids['frameworks']} = {{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (\n\t\t\t); runOnlyForDeploymentPostprocessing = 0; }};\n"
o+=f"\t\t{ids['resources']} = {{isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (\n\t\t\t); runOnlyForDeploymentPostprocessing = 0; }};\n"
o+=f"\t\t{ids['sources']} = {{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (\n"+"".join(f"\t\t\t\t{ids['bf_'+s]},\n" for s in srcs)+"\t\t\t); runOnlyForDeploymentPostprocessing = 0; };\n"
o+=f"\t\t{ids['maingroup']} = {{isa = PBXGroup; children = (\n\t\t\t\t{ids['srcgroup']},\n\t\t\t\t{ids['prodgroup']},\n\t\t\t); sourceTree = \"<group>\"; }};\n"
o+=f"\t\t{ids['srcgroup']} = {{isa = PBXGroup; children = (\n"+"".join(f"\t\t\t\t{ids['ref_'+s]},\n" for s in srcs)+"\t\t\t); path = Sources; sourceTree = \"<group>\"; };\n"
o+=f"\t\t{ids['prodgroup']} = {{isa = PBXGroup; children = (\n\t\t\t\t{ids['app']},\n\t\t\t); name = Products; sourceTree = \"<group>\"; }};\n"
o+=f"""\t\t{ids['target']} = {{
			isa = PBXNativeTarget;
			buildConfigurationList = {ids['cfg_tgt']};
			buildPhases = (
				{ids['sources']},
				{ids['frameworks']},
				{ids['resources']},
			);
			buildRules = (
			);
			dependencies = (
			);
			name = {NAME};
			productName = {NAME};
			productReference = {ids['app']};
			productType = "com.apple.product-type.application";
		}};
		{ids['proj']} = {{
			isa = PBXProject;
			attributes = {{
				BuildIndependentTargetsInParallel = 1;
				LastSwiftUpdateCheck = 2700;
				LastUpgradeCheck = 2700;
				TargetAttributes = {{
					{ids['target']} = {{
						CreatedOnToolsVersion = 27.0;
					}};
				}};
			}};
			buildConfigurationList = {ids['cfg_proj']};
			developmentRegion = en;
			hasScannedForEncodings = 0;
			knownRegions = (
				en,
				Base,
			);
			mainGroup = {ids['maingroup']};
			minimizedProjectReferenceProxies = 1;
			preferredProjectObjectVersion = 77;
			productRefGroup = {ids['prodgroup']};
			projectDirPath = "";
			projectRoot = "";
			targets = (
				{ids['target']},
			);
		}};
		{ids['cfg_proj_debug']} = {{
			isa = XCBuildConfiguration;
			buildSettings = {{{prj}				DEBUG_INFORMATION_FORMAT = dwarf;
				ENABLE_TESTABILITY = YES;
				GCC_OPTIMIZATION_LEVEL = 0;
				ONLY_ACTIVE_ARCH = YES;
				SWIFT_ACTIVE_COMPILATION_CONDITIONS = "DEBUG $(inherited)";
				SWIFT_OPTIMIZATION_LEVEL = "-Onone";
			}};
			name = Debug;
		}};
		{ids['cfg_proj_release']} = {{
			isa = XCBuildConfiguration;
			buildSettings = {{{prj}				DEBUG_INFORMATION_FORMAT = "dwarf-with-dsym";
				ENABLE_NS_ASSERTIONS = NO;
				SWIFT_COMPILATION_MODE = wholemodule;
				VALIDATE_PRODUCT = YES;
			}};
			name = Release;
		}};
		{ids['cfg_tgt_debug']} = {{
			isa = XCBuildConfiguration;
			buildSettings = {{{tgt}			}};
			name = Debug;
		}};
		{ids['cfg_tgt_release']} = {{
			isa = XCBuildConfiguration;
			buildSettings = {{{tgt}			}};
			name = Release;
		}};
		{ids['cfg_proj']} = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{ids['cfg_proj_debug']},
				{ids['cfg_proj_release']},
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
		{ids['cfg_tgt']} = {{
			isa = XCConfigurationList;
			buildConfigurations = (
				{ids['cfg_tgt_debug']},
				{ids['cfg_tgt_release']},
			);
			defaultConfigurationIsVisible = 0;
			defaultConfigurationName = Release;
		}};
	}};
	rootObject = {ids['proj']};
}}
"""
os.makedirs(f"{NAME}.xcodeproj/xcshareddata/xcschemes", exist_ok=True)
open(f"{NAME}.xcodeproj/project.pbxproj","w").write(o)
open(f"{NAME}.xcodeproj/xcshareddata/xcschemes/{NAME}.xcscheme","w").write(f"""<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion = "2700" version = "1.7">
   <BuildAction parallelizeBuildables = "YES" buildImplicitDependencies = "YES">
      <BuildActionEntries>
         <BuildActionEntry buildForTesting = "YES" buildForRunning = "YES" buildForProfiling = "YES" buildForArchiving = "YES" buildForAnalyzing = "YES">
            <BuildableReference BuildableIdentifier = "primary" BlueprintIdentifier = "{ids['target']}" BuildableName = "{NAME}.app" BlueprintName = "{NAME}" ReferencedContainer = "container:{NAME}.xcodeproj"/>
         </BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <LaunchAction buildConfiguration = "Debug" selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB" launchStyle = "0" useCustomWorkingDirectory = "NO" ignoresPersistentStateOnLaunch = "NO" debugDocumentVersioning = "YES" debugServiceExtension = "internal" allowLocationSimulation = "YES">
      <BuildableProductRunnable runnableDebuggingMode = "0">
         <BuildableReference BuildableIdentifier = "primary" BlueprintIdentifier = "{ids['target']}" BuildableName = "{NAME}.app" BlueprintName = "{NAME}" ReferencedContainer = "container:{NAME}.xcodeproj"/>
      </BuildableProductRunnable>
   </LaunchAction>
</Scheme>
""")
print("project written:", srcs)
