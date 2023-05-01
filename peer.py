import os
import sys
import time
import json
from socket import *
from threading import *
from cryptography.fernet import Fernet

#Declaring and initializing variables for P2P connections
directoryPath = os.path.dirname(os.path.realpath(__file__))

#Decalring CS and peer sock addresses
CS_IP = 'localhost'
if len(sys.argv) > 2 and int(sys.argv[2]):
    CS_PORT = int(sys.argv[2])
else:
    CS_PORT = 8000

IP = 'localhost'
if len(sys.argv) > 1 and int(sys.argv[1]):
    PORT = int(sys.argv[1]) 
else:
    PORT = 9000
peer_key = Fernet.generate_key()
peerFKey = Fernet(peer_key)
pSock = socket(AF_INET, SOCK_STREAM)
pSock.bind((IP, PORT))
pSock.listen(5)
peerId = ''
encFileMap = {}

#Funtion to display operations
def displayMenu():
    print("\n----------------OPERATIONS---------------")
    print("'create [filename] [access_rights]' - Create file")
    print("               Available access_rights:")
    print("                       1 - read-write")
    print("                       2 - read-only")
    print("                       3 - private")
    print("'read [filename]' - Reading a file")
    print("'write [filename]' - Write into a file")
    print("'restore [filename]' - Restore a file")
    print("'ls' - List all accessible files")
    print("'mkdir [foldername] [access_rights]' - Create a new folder with given permissions")
    print("'rm [filename]' - Delete a file")
    print("'rmdir [foldername]' - Delete a folder")
    print("'<exit>' - Exit from the file system.")
    print("----------------END OF MENU------------------")
    print()
    print("PLEASE ENTER ANY COMMAND AS SPECIFIED IN THE ABOVE FORMAT:")

#Function to check if the user entered choice is valid or not
def checkMenu(choice):
    cmdMap = {
        'create': 2,
        'write': 1,
        'read': 1,
        'delete': 1,
        'restore': 1,
        'ls': 0,
        'rmdir': 1,
        'mkdir': 2,
        '<exit>': 0
    }

    args = choice.split(' ')

    if args[0] in cmdMap:
        if len(args) != cmdMap[args[0]] + 1:
            print('{0}: Invalid command'.format(args[0]))
            time.sleep(3)
            return False
        if args[0] == 'write':
            (fName, fileExt) = os.path.splitext(args[1])
            if not fileExt:
                print('{0}: is not writable'.format(fName))
                time.sleep(3)
                return False
    else:
        print('\'{0}\' is not a recognized command'.format(args[0]))
        time.sleep(3)
        return False
    return True

fKey = b'iQYNEkkQxnQAfAZaOK0oNDNKfaHVmqn__YJ8Iv21Syk='
fernetKey = Fernet(fKey)

#Converting a dictionary to JSON and then encrypting it
def encryptChannel(dict):
    cpr = fernetKey.encrypt(json.dumps(dict).encode('ascii'))
    return cpr

#Decrypting the cipher and then converting json  back to dictionary
def decryptChannel(cpr):
    dictionary = json.loads(fernetKey.decrypt(cpr).decode('ascii'))
    return dictionary

#Functions to create response objects
def createErrorObj(errCode,errMessage):
    response = {
                'error': errCode,
                'errorMessage': errMessage
            }
    return response

#This code handles the actual communication between CS and a peer
def connectionHandler():
    CSSock = socket(AF_INET, SOCK_STREAM)
    try:
        CSSock.connect((CS_IP, int(CS_PORT)))
    except:
        print('Connecting to the CS failed! Try again.')

    while True:
        username = input('Please enter username/peername that is registered with CS: ')
        password = input('Enter password: ')
        CSSock.send(encryptChannel({
            'username': username,
            'password': password
        }))
        CSResponse = decryptChannel(CSSock.recv(1024))
        if 'error' in CSResponse:
            print(CSResponse['errorMessage'])
        else:
            print(CSResponse['message'])
        if 'error' not in CSResponse:
            break

    CSSock.send(encryptChannel({
        'IP': IP,
        'PORT': str(PORT)
    }))
    CSResponse = decryptChannel(CSSock.recv(1024).decode('ascii'))
    print(CSResponse['message'])

    global peerId
    peerId = CSResponse['pId']
    path = os.path.join(directoryPath, str(peerId))
    if not os.path.exists(path):
        os.mkdir(path)

    time.sleep(1)
    cmd = ''

    while '<exit>' not in cmd:
        displayMenu()
        cmd = input('')
        while not checkMenu(cmd):
            displayMenu()
            cmd = input('')

        CSSock.send(encryptChannel({
            'cmd': cmd
        }))
        cmdEntered = cmd.split()

        if cmdEntered[0] == 'create':
            CSResponse = decryptChannel(CSSock.recv(1024))

            if 'error' in CSResponse:
                print(CSResponse['errorMessage'])
                time.sleep(2)
                continue

            (fName, fileExt) = os.path.splitext(cmdEntered[1])
            encFileName = peerFKey.encrypt(fName.encode('ascii')).decode('ascii') + fileExt

            #Replicating in the owner
            path = os.path.join(directoryPath, peerId, encFileName)
            f = open(path, 'w')
            f.close()
            encFileMap[cmdEntered[1]] = encFileName

            request = {
                'cmd': cmd
            }
            print(CSResponse)

            #Replicating in other peers
            for key, value in CSResponse.items():
                peerIP = value['IP']
                peerPort = value['PORT']
                print('Creating {0} at {1}:{2}'.format(cmdEntered[1], peerIP, peerPort))
                peerSock = socket(AF_INET, SOCK_STREAM)
                peerSock.connect((peerIP, int(peerPort)))
                peerSock.send(encryptChannel(request))
                print('{0} replicated file successfully'.format(key))
                peerSock.close()
                time.sleep(1)

        elif cmdEntered[0] == 'read':
            CSResponse = decryptChannel(CSSock.recv(1024))
            if 'error' in CSResponse:
                print(CSResponse['errorMessage'])
            else:
                hasData = False
                #Checking if the file is present in the current peer
                if peerId in CSResponse['repPeerInfo']:
                    encFileName = encFileMap[cmdEntered[1]]
                    path = os.path.join(directoryPath, peerId, encFileName)
                    hasData = False

                    #Checking if file has been deleted
                    if os.path.exists(path):
                        print('file: {0} found in the current peer itself'.format(cmdEntered[1]))
                        encFile = Fernet(eval(CSResponse['encKey']))
                        data = []

                        with open(path, 'r') as f:
                            data = f.readlines()

                        if len(data) != 0:
                            decrypted_text = encFile.decrypt(eval(data[0])).decode('ascii')
                            print(decrypted_text)
                        else:
                            print('Requested file is Empty!')
                        hasData = True

                request = {
                    'cmd': cmd
                }
                #Checking if the file is present in the active peers
                for key, value in CSResponse['repPeerInfo'].items():
                    if hasData:
                        break
                    peerIP = value['IP']
                    peerPort = value['PORT']
                    print('Connecting to {0} using {1}:{2}'.format(key, peerIP, peerPort))
                    peerSock = socket(AF_INET, SOCK_STREAM)
                    peerSock.connect((peerIP, int(peerPort)))
                    peerSock.send(encryptChannel(request))
                    pRes = decryptChannel(peerSock.recv(1024))
                    if 'error' in pRes:
                        print(pRes['errorMessage'])
                    else:
                        if len(pRes['message']) != 0:
                            encFile = Fernet(eval(CSResponse['encKey']))
                            decrypted_text = encFile.decrypt(eval(pRes['message'][0])).decode('ascii')
                            print(decrypted_text)
                        else:
                            print('<file empty>')
                        hasData = True
                    time.sleep(1)

        elif cmdEntered[0] == 'write':
            CSResponse = decryptChannel(CSSock.recv(1024))
            if 'error' in CSResponse:
                print(CSResponse['errorMessage'])
                CSSock.send(encryptChannel({
                    'message': 'write Failed.'
                }))
                time.sleep(3)
            else:
                enteredData = ''
                inp = ''
                print('Type content you wish to write in a file. Type <exit> in a new line once you finish writing')
                print('Start typing below...')
                encFile = Fernet(eval(CSResponse['encKey']))
                while True:
                    inp = input()
                    if inp == '<exit>':
                        break
                    enteredData += inp + '\n'

                encData = str(encFile.encrypt(enteredData.encode('ascii')))
                

                if cmdEntered[1] in encFileMap:
                    encFileName = encFileMap[cmdEntered[1]]
                else:
                    encFileName = CSResponse['encrypted_file_name']

                path = os.path.join(directoryPath, peerId, encFileName)
                f = open(path, 'w+')
                f.write(encData)
                f.close()
                print('Write success!')

                for key, value in CSResponse['repPeerInfo'].items():
                    peerIP = value['IP']
                    peerPort = value['PORT']
                    print('Writing at {0}:{1}'.format(peerIP, peerPort))
                    peerSock = socket(AF_INET, SOCK_STREAM)
                    peerSock.connect((peerIP, int(peerPort)))
                    peerSock.send(encryptChannel({
                    'cmd': cmd,
                    'message': encData}))
                    print('{0}: write to {1} successful'.format(key, cmdEntered[1]))
                    time.sleep(1)
                CSSock.send(encryptChannel({
                    'message': 'SUCCESS'}))

        elif cmdEntered[0] == 'ls':
            CSResponse = decryptChannel(CSSock.recv(1024))
            #print(CSResponse)
            for data in CSResponse['message']:
                print(data)

        elif cmdEntered[0] == 'delete':
            CSResponse = decryptChannel(CSSock.recv(1024))
            if 'error' in CSResponse:
                print(CSResponse['errorMessage'])
            else:
                print(CSResponse['message'])

        elif cmdEntered[0] == 'restore':
            CSResponse = decryptChannel(CSSock.recv(1024))
            if 'error' in CSResponse:
                print(CSResponse['errorMessage'])
            elif CSResponse['message'] == 'REP_SUCCESS':
                encFileName = encFileMap[cmdEntered[1]]
                path = os.path.join(directoryPath, peerId, encFileName)
                request = {}
                #Checking if the file is deleted in the owner's file system.
                if not os.path.exists(path):
                    print('File not present!')
                else:
                    with open(path, 'r') as f:
                        data = f.readlines()
                    cnt = ''
                    for l in data:
                        cnt += l
                    request = {
                        'cmd': cmd,
                        'message': cnt
                    }
                    f.close()
                    for eachPeer in CSResponse['peers_to_replicate']:
                        peerIP = eachPeer['IP']
                        peerPort = eachPeer['PORT']
                        print('Replicating at {0}:{1}'.format(peerIP, peerPort))
                        peerSock = socket(AF_INET, SOCK_STREAM)
                        peerSock.connect((peerIP, int(peerPort)))
                        peerSock.send(encryptChannel(request))
                        time.sleep(1)

        elif cmdEntered[0] == 'mkdir':
            CSResponse = decryptChannel(CSSock.recv(1024))

            if 'error' in CSResponse:
                print(CSResponse['errorMessage'])
                time.sleep(2)
                continue

            encFolderName = peerFKey.encrypt(cmdEntered[1].encode('ascii')).decode('ascii')
            path = os.path.join(directoryPath, peerId, encFolderName)
            os.mkdir(path)
            encFileMap[cmdEntered[1]] = encFolderName

            request = {
                'cmd': cmd
            }
            for key, value in CSResponse.items():
                peerIP = value['IP']
                peerPort = value['PORT']
                print('Creating at {0}:{1}'.format(peerIP, peerPort))
                peerSock = socket(AF_INET, SOCK_STREAM)
                peerSock.connect((peerIP, int(peerPort)))
                peerSock.send(encryptChannel(request))
                print('{0} replicated file successfully'.format(key))
                peerSock.close()
                time.sleep(1)

        elif cmdEntered[0] == 'rmdir':
            CSResponse = decryptChannel(CSSock.recv(1024))

            if 'error' in CSResponse:
                print(CSResponse['errorMessage'])
                time.sleep(2)
                continue

            encFolderName = peerFKey.encrypt(cmdEntered[1]).decode('ascii')
            #Deleting the file in the owner and all in all other peers which replicated this
            path = os.path.join(directoryPath, peerId, encFolderName)
            os.rmdir(path)

            request = {
                'cmd': cmd
            }
            
            for key, value in CSResponse.items():
                peerIP = value['IP']
                peerPort = value['PORT']
                print('Connecting to {0} using {1}:{2}'.format(key, peerIP, peerPort))
                peerSock = socket(AF_INET, SOCK_STREAM)
                peerSock.connect((peerIP, int(peerPort)))
                peerSock.send(encryptChannel(request))
                print('{0} replication success!'.format(key))
                peerSock.close()
                time.sleep(1)


        time.sleep(2)
    CSSock.close()

def P2PrequestHandler(peerSock, sockAddr):
    peer_req = decryptChannel(peerSock.recv(1024))
    if not peer_req:
        return

    print('Processing the following request from the peer')
    print(':',peer_req['cmd'])

    cmdEntered = peer_req['cmd'].split()
    if cmdEntered[0] == 'create':
        (fName, fileExt) = os.path.splitext(cmdEntered[1])
        encFileName = peerFKey.encrypt(fName.encode('ascii')).decode('ascii') + fileExt
        path = os.path.join(directoryPath, peerId, encFileName)

        encFileMap[cmdEntered[1]] = encFileName
        f = open(path, 'w')
        print('File creation success!')
        f.close()
    elif cmdEntered[0] == 'mkdir':
        encFolderName = peerFKey.encrypt(cmdEntered[1].encode('ascii')).decode('ascii')
        path = os.path.join(directoryPath, peerId, encFolderName)
        os.mkdir(path)

        encFileMap[cmdEntered[1]] = encFolderName
    elif cmdEntered[0] == 'rmdir':
        encFolderName = peerFKey.encrypt(cmdEntered[1]).decode('ascii')
        path = os.path.join(directoryPath, peerId, encFolderName)
        os.rmdir(path)
    elif cmdEntered[0] == 'write' or cmdEntered[0] == 'restore':
        encFileName = encFileMap[cmdEntered[1]]
        path = os.path.join(directoryPath, peerId, encFileName)
        # extract content
        msg = peer_req['message']
        f = open(path, 'w+')
        f.write(msg)
        print('{0} Success!'.format(cmdEntered[0]))
        f.close()

    elif cmdEntered[0] == 'read':
        encFileName = encFileMap[cmdEntered[1]]
        path = os.path.join(directoryPath, peerId, encFileName)
        response = {}
        # Checking if file is deleted 
        if not os.path.exists(path):
            response = createErrorObj(404,'{0} could not be located at {1}'.format(cmdEntered[1], peerId))
        else:
            with open(path, 'r') as f:
                fileData = f.readlines() 
            f.close()
        peerSock.send(encryptChannel({'message': fileData}))

    elif cmdEntered[0] == 'delete':
        encFileName = encFileMap[cmdEntered[1]]
        path = os.path.join(directoryPath, peerId, encFileName)
        response = {}
        if not os.path.exists(path):
            response = createErrorObj(404,'{0} could not found at {1}'.format(cmdEntered[1], peerId))
        else:
            os.remove(path)
            if not os.path.exists(path):
                response = {
                    'message': '{0} deleted {1} successfully'.format(peerId, cmdEntered[1])
                }
            else:
                response = createErrorObj(400,'Failed to delete the file: {0}'.format(cmdEntered[1]))
        if 'error' in response:
            print(response['message'])
        else:
            print(response['message'])
        peerSock.send(encryptChannel(response))

    elif cmdEntered[0] == 'FileList':
        path = os.path.join(directoryPath, peerId)
        files = os.listdir(path)
        decFileNames = []
        for file in files:
            try:
                (fName, fileExt) = os.path.splitext(file)
                decFile = peerFKey.decrypt(fName.encode('ascii')).decode('ascii') + fileExt
                decFileNames.append(decFile)
            except:
                decFileNames.append(file)
        response = {
            'pId': peerId,
            'listOfFiles': decFileNames
        }
        peerSock.send(encryptChannel(response))
    else:
        print("Invalid Command. Please enter a valid command.")

def main():
    handleMenu = Thread(target = connectionHandler)
    handleMenu.start()

    while True:
        peerSock, sockAddr = pSock.accept()
        P2PrequestThread = Thread(target = P2PrequestHandler, args=(peerSock, sockAddr))
        P2PrequestThread.start()

if __name__ == '__main__':
    main()

pSock.close()

