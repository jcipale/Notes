#!/bin/csh

echo "Musica V1.1 Build mechanism"
sleep 3

tar -czf Musica_v1.1.tar.gz \
    --exclude-from=tar_exclude_musica.txt \
    ./

echo "____________________________________________________"
echo "confirm tarball contents"
sleep 2

tar -tvf Musica_v1.1.tar.gz
sleep 5

echo "____________________________________________________"

echo "Do the contents of the tarball match the expected manifest (Y/N)?"
set answer = $<

if ("$answer" == "Y" || "$answer" == "y") then
    echo "Build Notes release..."
	# commands to run
	git add  Musica_v1.1.tar.gz RELEASE/.
	git commit -m "Musica Release delviered"
	git push
else if ("$answer" == "N" || "$answer" == "n") then
    echo "Check tar exclude file for correctness."
endif

echo "Notes V1.0 Build mechanism"
sleep 3

cd ./web

tar -czf Notes_v1.0.tar.gz \
    --exclude-from=tar_exclude_notes.txt \
    ./

echo "____________________________________________________"
echo "confirm tarball contents"
sleep 2

tar -tvf Notes_v1.0.tar.gz
sleep 5

echo "____________________________________________________"

echo "Do the contents of the tarball match the expected manifest (Y/N)?"
set answer = $<

if ("$answer" == "Y" || "$answer" == "y") then
    echo "Build Notes release..."
	# commands to run
	git add  Notes_v1.0.tar.gz RELEASE/.
	git commit -m "Musica Release delviered"
	git push
else if ("$answer" == "N" || "$answer" == "n") then
    echo "Check tar exclude file for correctness."
endif

exit 0
