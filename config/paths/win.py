# coding=utf-8
# diese Pfade bitte nicht ändern, sondern in der user.py überschreiben,
# da diese Datei bei Updates überschrieben wird
from os.path import expanduser, join
rsync = r"C:\MinGW\msys\1.0\bin\rsync.exe"
git = r"C:\Program Files\Git\bin\git.exe"
ssh = r"C:\Program Files\Git\bin\ssh.exe"
mysql = r"C:\Program Files\MySQL\MySQL Workbench 6.3 CE\mysql.exe"
java = r""
jameica_cmd = [r"C:\Program Files\Java\jre1.8.0_40\bin\javaw.exe", "-Xmx256m",
               "-jar", r"C:\Program Files\jameica\jameica-win32.jar"]
jameica_cwd = r"C:\Program Files\jameica"
jameica_properties = join(expanduser("~"), ".jameica.properties")