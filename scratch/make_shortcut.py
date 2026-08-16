import os
import subprocess

vbs_content = r'''Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "C:\Users\Administrator\Desktop\AI Digital Marketing Command Center.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "C:\Users\Administrator\Desktop\AI-Digital-Marketing\corporate-cars-social-agent\.venv\Scripts\pythonw.exe"
oLink.Arguments = "C:\Users\Administrator\Desktop\AI-Digital-Marketing\scripts\launch_dashboard.py"
oLink.WorkingDirectory = "C:\Users\Administrator\Desktop\AI-Digital-Marketing"
oLink.Description = "Launch AI Digital Marketing Dashboard"
oLink.Save
'''

vbs_path = "create_shortcut.vbs"
with open(vbs_path, "w", encoding="utf-8") as f:
    f.write(vbs_content)

subprocess.run(["cscript", "//nologo", vbs_path], check=True)
if os.path.exists(vbs_path):
    os.remove(vbs_path)
print("Desktop Shortcut Created Successfully!")
