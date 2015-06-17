# coding=utf-8
# diese Pfade bitte nicht ändern, sondern in der user.py überschreiben,
# da diese Datei bei Updates überschrieben wird
from os.path import expanduser, join
git = r"C:\Program Files\Git\bin\git.exe"
java = r"C:\ProgramData\Oracle\Java\javapath\java.exe"
jameica_cmd = [java, "-Xmx256m",
               "-jar", r"C:\Program Files\jameica\jameica-win32.jar"]
jameica_cwd = r"C:\Program Files\jameica"
jameica_properties = join(expanduser("~"), ".jameica.properties")