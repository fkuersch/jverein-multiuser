# diese Pfade bitte nicht ändern, sondern in der user.py überschreiben,
# da diese Datei bei Updates überschrieben wird
from os.path import expanduser, join
git = "/usr/bin/git"
java = "/usr/bin/java"
jameica_cmd = ["/Applications/jameica.app/jameica-macos64.sh"]
jameica_cwd = None
jameica_properties = join(expanduser("~"), ".jameica.properties")
