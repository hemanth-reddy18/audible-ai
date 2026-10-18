@echo off
set "JAVA_HOME=C:\Users\ACER\OneDrive\Documents\careofsearch(cos)\tools\jdk"
set "ANDROID_HOME=C:\Users\ACER\OneDrive\Documents\careofsearch(cos)\tools\android-sdk"
set "PATH=%JAVA_HOME%\bin;%PATH%"
cd /d "%~dp0"
call "C:\Users\ACER\OneDrive\Documents\careofsearch(cos)\tools\gradle\gradle-8.7\bin\gradle.bat" assembleDebug
