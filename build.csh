#!/bin/csh

# Set path variables
set BASE = /mnt/stor1/Develop/Notes
set DOCS = docs
set REL = RELEASE

echo "Musica V1.1 Build mechanism"
sleep 3

# Read/prompt for build_ver value
if ($#argv >= 1) then
    set RelVer = "$argv[1]"
else
    echo "Enter the Release Version: "
    set RelVer = "$<"
endif

echo "Release Version: " $RelVer

#--------------------------------------------------
#     Convert docs to pdf
#--------------------------------------------------
mkdir $BASE/$REL/$RelVer

cd $BASE/$DOCS

ls -l | grep *.doc

sleep 2

foreach file (*.doc)
    libreoffice --headless --convert-to pdf --outdir $BASE/$REL/$RelVer $file
end

#--------------------------------------------------
#      Create Musica tarball and inspect results
#--------------------------------------------------
cd $BASE

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
	mv Musica_v1.1.tar.gz $BASE/$REL/$RelVer/.
else if ("$answer" == "N" || "$answer" == "n") then
    echo "Check tar exclude file for correctness."
endif

echo "Notes V1.0 Build mechanism"
sleep 3

cd ./web

#--------------------------------------------------
#      Create Notes tarball and inspect results
#--------------------------------------------------

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
	mv Notes_v1.0.tar.gz $BASE/$REL/$RelVer/. 
	cd ..
else if ("$answer" == "N" || "$answer" == "n") then
    echo "Check tar exclude file for correctness."
endif

#----------- temp debug -----------
echo "hostname: " `hostname`
echo "whoami:   " `whoami`
echo "root:     " `pwd`

ls -ld /usr /usr/bin

echo "Git binary:"
ls -l /usr/bin/git

echo "Git version:"
/usr/bin/git --version

cd $BASE

git add $REL/$RelVer
git add $REL/$RelVer/*.gz
git add $REL/$RelVer/*.pdf
git commit -m "Commit tarball builds"
git push

echo "Build completed"

exit 0
