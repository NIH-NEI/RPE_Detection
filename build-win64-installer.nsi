
!define VERSION "1.2.0"
!define PATCH  "1"
!define INST_DIR "dist\RPE_Detection"

Var START_MENU

!include "MUI2.nsh"

# set "Program Files" as install directory
InstallDir $PROGRAMFILES64\RPE_Detection
 
;define installer name
Name "RPE Detection 1.2.0"
OutFile "dist\RPE_Detection-1.2.0-win64.exe"

;SetCompressor lzma

!define MUI_HEADERIMAGE
!define MUI_ABORTWARNING

!define MUI_ICON Icons\RPE_Detection256x256.ico
;!define MUI_UNICON Icons\RPE_Detection256x256.ico

Function ConditionalAddToRegisty
  Pop $0
  Pop $1
  StrCmp "$0" "" ConditionalAddToRegisty_EmptyString
    WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\RPE Detection" \
    "$1" "$0"
    ;MessageBox MB_OK "Set Registry: '$1' to '$0'"
    DetailPrint "Set install registry entry: '$1' to '$0'"
  ConditionalAddToRegisty_EmptyString:
FunctionEnd

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "Help\License.txt"
!insertmacro MUI_PAGE_DIRECTORY

!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English" ;first language is the default language
 
# default section start
Section "-Core installation"

; Install for all users
SetShellVarContext all
 
# define output path
SetOutPath $INSTDIR
 
# specify file to go in output path
File /r dist\RPE_Detection\*.*

WriteRegStr SHCTX "Software\National Eye Institute\RPE Detection" "" $INSTDIR
 
# define uninstaller name
WriteUninstaller $INSTDIR\uninstall.exe

Push "DisplayName"
Push "RPE Detection"
Call ConditionalAddToRegisty
Push "DisplayVersion"
Push "1.2.0"
Call ConditionalAddToRegisty
Push "Publisher"
Push "National Eye Institute"
Call ConditionalAddToRegisty
Push "UninstallString"
Push "$INSTDIR\uninstall.exe"
Call ConditionalAddToRegisty
Push "NoRepair"
Push "1"
Call ConditionalAddToRegisty
Push "DisplayIcon"
Push "$INSTDIR\__main__.exe,0"
Call ConditionalAddToRegisty
  
;Create shortcuts
CreateDirectory "$SMPROGRAMS\RPE Detection"
CreateShortCut "$SMPROGRAMS\RPE Detection\RPE Detection.lnk" "$INSTDIR\__main__.exe"
CreateShortCut "$SMPROGRAMS\RPE Detection\Uninstall RPE Detection.lnk" "$INSTDIR\uninstall.exe"
CreateShortCut "$DESKTOP\RPE Detection.lnk" "$INSTDIR\__main__.exe"

; Write special uninstall registry entries
Push "StartMenu"
Push "RPE Detection"
Call ConditionalAddToRegisty

#-------
# default section end
SectionEnd
 
# create a section to define what the uninstaller does.
# the section will always be named "Uninstall"
Section "Uninstall"

; UnInstall for all users
SetShellVarContext all
 
ReadRegStr $START_MENU SHCTX \
   "Software\Microsoft\Windows\CurrentVersion\Uninstall\RPE Detection" "StartMenu"

 
# Always delete uninstaller first
Delete $INSTDIR\uninstall.exe
 
# now delete installed files
RMDir /r /REBOOTOK $INSTDIR

; Remove the registry entries.
DeleteRegKey SHCTX "Software\National Eye Institute\RPE Detection"
DeleteRegKey SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\RPE Detection"

Delete "$SMPROGRAMS\RPE Detection\Uninstall RPE Detection.lnk"
Delete "$SMPROGRAMS\RPE Detection\RPE Detection.lnk"
Delete "$DESKTOP\RPE Detection.lnk"

DeleteRegKey /ifempty SHCTX "Software\National Eye Institute\RPE Detection"

SectionEnd

Function .onInit
  ReadRegStr $0 SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\RPE Detection" "UninstallString"
  StrCmp $0 "" inst

  MessageBox MB_YESNOCANCEL|MB_ICONEXCLAMATION \
  "RPE Detection is already installed. $\n$\nDo you want to uninstall the old version before installing the new one?" \
  /SD IDYES IDYES uninst IDNO inst
  Abort

;Run the uninstaller
uninst:
  ClearErrors
  StrLen $2 "\uninstall.exe"
  StrCpy $3 $0 -$2 # remove "\uninstall.exe" from UninstallString to get path
  ExecWait '"$0" /S _?=$3' ;Do not copy the uninstaller to a temp file

  IfErrors uninst_failed inst
uninst_failed:
  MessageBox MB_OK|MB_ICONSTOP "Uninstall failed."
  Abort

inst:
  ClearErrors

FunctionEnd

