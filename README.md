TODO: this is still work in progress. please hold the line...



# jverein-multiuser: jVerein mit mehreren Benutzern verwenden

jverein-multiuser bietet Multiuser-Support für jVerein mit beliebig vielen Nutzern. Dafür werden die gesamten Jameica-Daten mit dem Versionskontrollsystem Git verwaltet und in einem Online-Repository gespeichert.



## Features

### Multiuser-Support

Dieses Script bietet Multiuser-Support für jVerein mit beliebig vielen Nutzern. Dabei wird die Vereinsverwaltung für alle anderen Nutzer gesperrt, sobald ein Nutzer jVerein startet. Sollte jVerein bereits durch eine andere Person gesperrt sein, wird eine Meldung mit deren Namen angezeigt.

### Versionskontrolle

#### Nachvollziehbarkeit

Im Git-Repository kann nachvollzogen werden, wer wann welche Änderungen vorgenommen hat. Dazu hinterlässt jeder Nutzer nach jeder Änderung eine kurze Nachricht (commit message). Die Datenbanken werden als Text (SQL-Export) gespeichert, was die Nachvollziehbarkeit von Änderungen erleichtert.

#### Git-Commits als Savepoints

Falls kritische Änderungen missglücken, kann man die Änderungen verwerfen und die gesamte Vereinsverwaltung wird zum vorherigen Stand zurückgesetzt. So kann man z. B. Updates oder Abrechnungen gefahrlos testen.

#### Externes Backup

Falls die lokalen Dateien verloren gehen oder beschädigt werden, ist eine weitere Version immer noch im Online-Repository vorhanden (inklusive der gesamten Historie). Es ist natürlich trotzdem sehr empfehlenswert, regelmäßig weitere Backups anzulegen - ggf. auch automatisch über das Online-Repository.

### Benutzerspezifische Jameica-Einstellungen

Jameica-Einstellungen, wie z. B. die Fenster-Größe oder die zuletzt geöffneten Ordner, werden vor dem Start für den jeweiligen Nutzer eingerichtet und lokal gespeichert, nachdem das Programm beendet wurde.

### Synchronisation von Updates

jverein-multiuser stellt sicher, dass alle Nutzer die gleiche Jameica-Version benutzen. Wenn ein Nutzer Jameica aktualisiert, werden alle anderen Nutzer ebenfalls aufgefordert, ein Update durchzuführen. Die Plugins (Hibiscus, Jverein, ...) befinden sich im Repository und werden deshalb automatisch synchronisiert.

### Export von E-Mail-Adressen

Die E-Mail-Adressen aller aktuellen Mitglieder werden in die Datei 'dump/mitglieder-emails.csv' exportiert.

Diese Liste kann verwendet werden, um die Abonnenten einer Mitglieder-Mailingliste zu aktualisieren, z. B. mit mailman sync_members: http://manpages.org/sync_members/8



## FAQ - Häufige Fragen

### An wen richtet sich jverein-multiuser?

jverein-multiuser richtet sich an Vereine, die jVerein mit mehreren Personen nutzen möchten und/oder "Savepoints" brauchen, um Fehler in der Bedienung von jVerein einfach rückgängig machen zu können. jverein-multiuser ist ein reines Terminal-Programm und setzt Grundkenntnisse mit Git voraus.

### Ist jverein-multiuser sicher?

Nein. Fast alle Daten im Repository sind unverschlüsselt. Konfigurationsdateien und die jVerein-Datenbank sind ohnehin nicht verschlüsselt, zusätzlich werden alle Datenbanken als Klartext im Repository abgelegt. Die Hibiscus-Datenbank wird dazu entschlüsselt.

Da das Repository sensible Mitglieder- und Finanzdaten enthält, ist wichtig, selbst für die Sicherheit der Daten zu sorgen. Hier einige Tipps (wie die genau umgesetzt werden können, sprengt allerdings den Rahmen dieser Dokumentation):

Online- und Offline-Repositories auf einer verschlüsselten Festplatte oder in einem verschlüselten Container speichern, aktuelle Anti-Viren-Software verwenden, Online-Repository nur für die Nutzer von jVerein verfügbar machen, nur Zugang per SSH erlauben, dabei Passwort-Authentifizierung abschalten, nur Key-basierte Authentifizierung mit sicheren Keys erlauben, ...

Dass alle Datenbanken im Klartext-Format im Repository abgelegt werden, hat in erster Linie einen technischen Grund: Git kann mit Änderungen von Binärdaten (wie die Datenbank-Dateien) nicht gut umgehen - das Repository würde nach einigen Monaten oder Jahren der Nutzung mehrere GB in Anspruch nehmen, die Synchronisation wäre entsprechend langsam.

Der Export als Klartext hat zudem den Vorteil, dass Änderungen an den Datenbanken einfacher nachvollziehbar sind. Dadurch, dass bei jedem Start die Datenbanken neu angelegt werden, werden [Updates der Datenbank auf die aktuelle Datenbank-Engine](https://jverein-forum.de/viewtopic.php?t=4525) automatisch durchgeführt.

### Kann ich die Versionskontrolle auch ohne online verfügbares Git-Repository verwenden?

Ja. Dazu kann ein weiteres Repository auf der Festplatte angelegt werden, das dann als Pseudo-Online-Repository dient. Dies ist unten in der Installationsanleitung beschrieben.

### Läuft jverein-multiuser unter Windows/macOS/Linux?

Ja.

### Wie funktioniert das Sperren für andere Nutzer (Lock-File)?

Beim Start aktualisiert jverein-multiuser das Git-Repository (git pull) und prüft, ob es ein [Tag](https://git-scm.com/book/en/v2/Git-Basics-Tagging) gibt, das mit "lock" anfängt. Sollte solch ein Tag existieren, verweigert das Script den Start von jVerein und gibt den Namen des Tags aus (dieser enthält u. A. den Namen der Person, die das Tag angelegt hat). Sollte beim Start kein solches Tag existieren, wird ein neues angelegt und ins Online-Repository hochgeladen. Dann wird jVerein gestartet.

Nach dem Beenden von jVerein, der Eingabe einer Commit-Message und dem pushen des aktuellen Standes ins Online-Repository wird das Tag wieder entfernt.

Dadurch, dass das Aktualisieren des Repositories und das Anlegen und Hochladen des Tags einzelne Operationen sind alle etwas Zeit in Anspruch nehmen, gibt es eine Race Condition: Wenn zwei Nutzer exakt zur gleichen Zeit das Lock anfordern, wird jVerein bei beiden Nutzern gestartet. Dieses Szenario ist allerdings so unwahrscheinlich, dass es für diese Zwecke akzeptabel ist. Selbst wenn es eintritt, stellt Git beim Hochladen eine Kollision fest. Ein Nutzer muss dann ggf. seine Änderungen verwerfen.

### Gibt es Alternativen?

Ja, es gibt diverse alternative Ansätze, Multiuser-Fähigkeit für jVerein umzusetzen. Diese sind in der jVerein-Dokumentation beschrieben: https://doku.jverein.de/allgemein/multiuser

### Voraussetzungen

Unterstützt wird die [Standardinstallation](https://doku.jverein.de/allgemein/installation) von Jameica, Hibiscus und jVerein mit mindestens Jameica 2.6.3

* Sehr empfehlenswert ist die Installation von Jameica per [Hibiscus-Mashup](https://hibiscus-mashup.derrichter.de/), da diese Installation eine Java-Umgebung mitbringt
* Datenbank: H2 (Standard), nicht MySQL



## Installieren

### Windows 10

#### Git installieren

Git herunterladen: https://git-scm.com/download/win

Installer ausführen.

Windows-Explorer-Integration wird nicht benötigt.

nano ist als Standard-Editor für Anfänger empfehlenswert.

#### Jameica installieren

Hibiscus-Mashup (Windows 64-Bit) herunterladen: https://hibiscus-mashup.derrichter.de/index.php/download

Installer ausführen.

Jameica am Ende der Installation nicht starten.

#### jverein-multiuser installieren

jverein-multiuser herunterladen: https://github.com/fkuersch/jverein-multiuser/releases/latest/download/jverein-multiuser.exe

Git bash öffnen

```
mkdir -p bin
mv Downloads/jverein-multiuser.exe bin/
```



### macOS 10.14

#### Git installieren

Terminal öffnen.

```
git --version
```

Installations-Assistenten folgen.

#### Jameica installieren

Hibiscus-Mashup (macOS 10.10+) herunterladen: https://hibiscus-mashup.derrichter.de/index.php/download

DMG öffnen und Installer ausführen (ggf. per Rechtsklick, Öffnen).

#### jverein-multiuser installieren

Terminal öffnen

```
# jverein-multiuser herunterladen
cd Downloads
curl -LO https://github.com/fkuersch/jverein-multiuser/releases/latest/download/jverein-multiuser_macos.zip

# entpacken
unzip jverein-multiuser_macos.zip

# nach ~/bin verschieben
mkdir -p ~/bin
mv jverein-multiuser ~/bin/

# ~/bin in $PATH aufnehmen
echo 'export PATH="$PATH:~/bin"' >> ~/.profile
source ~/.profile  # oder Terminal neu starten
```



### Ubuntu 19.10

#### Installation von Jameica, Git und jverein-multiuser

Hibiscus-Mashup (Linux 64-Bit) herunterladen: https://hibiscus-mashup.derrichter.de/index.php/download

Terminal öffnen

```
# Git installieren:
sudo apt update && sudo apt install -y git

# Hibiscus-Mashup installieren:
cd ~/Downloads
chmod +x Jameica-Hibiscus_Linux64-Installer.run
./Jameica-Hibiscus_Linux64-Installer.run

# jverein-multiuser herunterladen und installieren:
wget https://github.com/fkuersch/jverein-multiuser/releases/latest/download/jverein-multiuser_linux.zip
unzip jverein-multiuser_linux.zip
mkdir -p ~/bin
mv jverein-multiuser ~/bin/
source ~/.profile  # oder Terminal-Fenster neu starten
```



## Einrichten

### Remote-Repository einrichten

Wenn die Daten auf dem lokalen Rechner verbleiben sollen, kann ein Git-Repository angelegt werden, das dann als Remote-Repository verwendet wird:

```
cd
git init --bare .jverein-multiuser-remote-repo.git
```

Wenn stattdessen ein (privates und gut geschütztes!) Online-Repository verwendet werden soll, dieses jetzt einrichten.

### jverein-multiuser konfigurieren

jverein-multiuser das erste Mal starten:

```
jverein-multiuser
```

Hierbei wird das Arbeitsverzeichnis unter ~/.jverein-multiuser erzeugt und eine Beispiel-Konfigurationsdatei angelegt: ~/.jverein-multiuser/user_config.ini

Diese bearbeiten:

```
nano ~/.jverein-multiuser/user_config.ini
```

Das Raute-Symbol am Anfang jeder Zeile (#) entfernen und Beispiel-Namen und E-Mail-Adresse ersetzen. Wenn jverein-multiuser von der gleichen Person auf unterschiedlichen Computern verwendet wird, muss die Option "computer" auf jedem System einen anderen Wert haben.

Bei "remote" die URL zum Repository eingeben. In unserem Beispiel:

```
remote = /home/BENUTZER/.jverein-multiuser-remote-repo.git
```

Achtung: Der Pfad muss hier absolut sein, "/home/BENUTZER" kann nicht mit "~" abgekürzt werden.

Speichern mit *Ctrl+O, Enter*. Beenden mit *Ctrl+X*.

### Jameica das erste Mal starten

jverein-multiuser erneut starten:

```
jverein-multiuser
```

Mit *j, Enter* wird das lokale Repository eingerichtet.

Wenn das erfolgreich war, *s, Enter* drücken, um Jameica zu starten.

### Option A: Neue Jameica-Installation einrichten

Da Jameica mit einem neuen, leeren Arbeitsverzeichnis gestartet wurde, sind weder Plugins (z. B. Hibiscus, jVerein) noch Daten vorhanden. Diese nun installieren und einrichten. Bei der Installation der Plugins darauf achten, dass die Plugins im Jameica-Arbeitsverzeichnis gespeichert werden. So werden sie in die Versionskontrolle aufgenommen und allen Nutzern steht die gleiche Version zur Verfügung.

Nach dem Installieren von Plugins muss Jameica beendet und neu gestartet werden. Dazu in jverein-multiuser *s, Enter* eingeben.

Danach Jameica schließen.

Wenn Jameica per Hibsicus-Mashup installiert wurde (wie oben beschrieben), oder wenn eine bestehende Jamaica-Installation mitsamt Plugins und Daten mit jverein-multiuser gentutz werden soll, bietet es sich an, die Option B zu wählen:

### Option B: Vorhandenes Jameica-Arbeitsverzeichnis kopieren

Jameica wieder beenden und ein neues Terminal-Fenster öffnen.

Im neuen Terminal das gerade durch den ersten Start erzeugte Arbeitsverzeichnis löschen:

```
rm -rf ~/.jverein-multiuser/repo/jameica/
```

Und das bisher genutzte Jameica-Arbeisverzeichnis kopieren. Unter `~/.jameica` wurden durch die Installation mit Hibiscus-Mashup bereits diverse Plugins mitinstalliert, und typischerweise befindet sich dort auch das Jameica-Arbeitsverzeichnis, wenn Jameica vorher bereits genutzt wurde. Wenn das Verzeichnis abweicht, muss dies im folgenden Befehl ggf. geändert werden:

```
cp -r ~/.jameica/ ~/.jverein-multiuser/repo/jameica
```

Nun kann das 2. Terminal-Fenster wieder geschlossen werden.

### Erster Commit

Nach dem Beenden von Jameica sollen die Änderungen gespeichert und hochgeladen werden.

Dazu in jverein-multiuser mit *f, Enter* bestätigen, dass der aktuelle Arbeitsschritt abgeschlossen ist (dazu s. u.: Tipps).

Dann mit *j, Enter* bestätigen, dass die Änderungen hochgeladen werden sollen.

Nun eine kurze Zusammenfassung eingeben, was geändert wurde (z. B. "Aufnahme Mitglieder") und mit *Enter* bestätigen.

Die Änderungen werden nun hochgeladen.



## jverein-multiuser deinstallieren

jverein-multiuser macht Änderungen am Arbeitsverzeichnis, sodass Jameica nicht ohne weiteres mit diesem Arbeitsverzeichnis gestartet werden kann.

### Jameica starten und beenden

Um die Änderungen rückgängig zu machen, muss Jameica wie gewohnt über jverein-multiuser gestartet und danach direkt wieder geschlossen werden. In jverein-multiuser warten, bis "jVerein wurde beendet." erscheint.

### Jameica-Arbeitsverzeichnis kopieren

In diesem Zustand ist das Arbeitsverzeichnis für Jameica nutzbar, kann also kopiert werden.

Dazu ein neues Terminal-Fenster öffnen.

Achtung, die Dateien in `~/.jameica` werden dabei überschrieben! Falls dieses Verzeichnis bereits existiert, ggf. in folgendem Befehl ändern:

```
cp -r ~/.jverein-multiuser/repo/jameica ~/.jameica
```

### Programm entfernen

```
rm ~/bin/jverein-multiuser
```



## Tipps

### Änderungen schrittweise durchführen

Änderungen am Arbeitsverzeichnis können nach dem Schließen von Jameica als sogenannter Git-Commit in die Versionskontrolle aufgenommen werden. Wenn man Fehler in Jameica bzw. jVerein macht, kann jverein-multiuser die aktuellen Änderungen verwerfen und zum letzten Commit zurückspringen.

Deshalb empfiehlt es sich, im Arbeitsablauf in kleinen Schritten vorzugehen und die Änderungen jeweils direkt zu committen. Bei Mitgliedsbeitrags-Abrechnungen könnte das z. B. so aussehen: 1. Ein- und Austritte bearbeiten, 2. Kontoumsätze abrufen und buchen, 3. Mahnungen bearbeiten, 4. Abrechnung erstellen, prüfen und Pre-Notifications verschicken. Nach jedem Schritt Jameica beenden und in jverein-multiuser einen neuen Commit anlegen.

### Häufige Passwortabfragen für SSH-Key verhindern

Wenn das Remote-Repository mit SSH und einem SSH-Key genutzt wird, fragt Git bei jeder Operation nach dem Passwort für den Key. Diese Abfragen können mit ssh-agent minimiert werden.

https://help.github.com/en/github/authenticating-to-github/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#adding-your-ssh-key-to-the-ssh-agent

