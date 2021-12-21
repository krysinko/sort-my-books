# https://github.com/kuhnchris/mobi-python - for python 3+
from mobi import Mobi
import os, json, pprint, shutil

sources = ["./test"]
destination = "./test"

fileList = {}
mobi = '.mobi'
epub = '.epub'
pdf = '.pdf'


def addExt(root, f, extension):
    fullPath = os.path.join(root, f.replace(extension, ''))
    exts = fileList.get(fullPath)
    if exts is None:
        exts = {extension: True}
    else:
        exts.update({extension: True})

    fileList.update({fullPath: exts})


def createAuthorDir(author):
    print(destination + author, os.path.exists(destination + author))
    if not os.path.exists(destination + author):
        os.mkdir(destination + author)

def goThroughSource(s):
    for root, dirs, files in os.walk(s):
        # print(root, dirs, files)
        if len(files):
            for file in files:
                if file.find(mobi) > 0:
                    addExt(root, file, mobi)
                elif file.find(epub) > 0:
                    addExt(root, file, epub)
                elif file.find(pdf) > 0:
                    addExt(root, file, pdf)
                else:
                    pass

        # else: pass

for s in sources:
    goThroughSource(s)

filesWithErrorDuringCopy = []
for x in fileList:
    if fileList.get(x) and (fileList.get(x)).get(mobi) is not None:
        book = Mobi(f'{x + mobi}')
        book.parse();
        print(x + mobi)
        createAuthorDir(book.authorName)
        for ext in fileList[x]:
            try:
                shutil.copy(x + ext, destination + book.authorName + '/' + book.newFileName + ext)
            except OSError:
                print('Error copy: ', x + ext)
                filesWithErrorDuringCopy.append(x + ext)

print(len(filesWithErrorDuringCopy), " files couldn't be copied. List:\n")
for f in filesWithErrorDuringCopy:
    print(f)




