import os
import sys
import json
import random
from socket import *
from threading import *
from cryptography.fernet import Fernet

#Declaring and initializing variables for P2P connections
IP = 'localhost'
if len(sys.argv) > 1 and int(sys.argv[1]):
    PORT = int(sys.argv[1]) 
else:
    PORT = 8000

RC = 3
serverSock = socket(AF_INET, SOCK_STREAM)
serverSock.bind((IP, PORT))
serverSock.listen(5)
print('Started CS with IP: {0} and PORT: {1}'.format(IP, PORT))
totalPeers = 0
activePeers = {}
allPeersData = {}
directoryPath = os.path.dirname(os.path.realpath(__file__))

# fKey = b'Z4-L_1FMlhMiHJgNtI5hCyry2nV6-brcEW2lOsFZ7K8='
fKey = b'iQYNEkkQxnQAfAZaOK0oNDNKfaHVmqn__YJ8Iv21Syk='
fernetKey = Fernet(fKey)


#Converting a dictionary to JSON and then encrypting it
def encryptChannel(dict):
    cipher = fernetKey.encrypt(json.dumps(dict).encode('ascii'))
    return cipher

#Decrypting the cipher and then converting json  back to dictionary
def decryptChannel(cpr):
    dictionary = json.loads(fernetKey.decrypt(cpr).decode('ascii'))
    return dictionary

#writing lod data into files
def writeLogData(file_content, path):
    path = os.path.join(directoryPath, path)
    with open(path, "w") as write_file:
        json.dump(file_content, write_file, indent=4)

#Storing all peer details
peerDetails = {}

#Functions to create response objects
def createErrorObj(errCode,errMessage):
    response = {
                'error': errCode,
                'errorMessage': errMessage
            }
    return response

#Functions to create response objects
def createSuccObj(message):
    response = {
                'message': message
            }
    return response

#Function to handle replications
def replicationHandler(n = RC):
    n = len(activePeers) if n > len(activePeers) else n
    randIdx = random.sample(range(0, len(activePeers)), n)
    activePeers_ids = list(activePeers.keys())
    replicatedPeers = []

    for idx in randIdx:
        replicatedPeers.append(activePeers_ids[idx])

    return replicatedPeers

def registeringPeer():
    while True:
        usrIp = input("Enter username and password of the peer to register in CS. Enter as 'peername password'\n")
        usrIpSplit = usrIp.split()

        if len(usrIpSplit) == 2:
            [username, password] = usrIpSplit
            peerDetails[username] = password
            print('Peer register success with Username:{0} and Password: {1}'.format(username,password))
        else:
            print("Registration failed! Please enter peername and password in the correct format.")


#Function to Handle peer requests
def peerRequestHandler(peerSock, sockAddr):
    userCred = decryptChannel(peerSock.recv(1024))

    while True:
        username = userCred['username']
        password = userCred['password']

        if username in peerDetails and peerDetails[username] == password:
            response = createSuccObj('Login Successfull!')
            peerSock.send(encryptChannel(response))
            break
        else:
            response = createErrorObj(401,'Username & Password combination doesn\'t exist')
            peerSock.send(encryptChannel(response))
        userCred = decryptChannel(peerSock.recv(1024))

    global totalPeers
    totalPeers += 1
    peerId = 'peer_{0}'.format(totalPeers)

    peerData = decryptChannel(peerSock.recv(1024))
    peerSock.send(encryptChannel({
        'message': 'Peer {0}, is connected to CS!'.format(totalPeers),
        'pId': peerId
    }))
    activePeers[peerId] = {
        'IP': peerData['IP'],
        'PORT': peerData['PORT']
    }
    writeLogData(activePeers, 'activePeers.json')
    writeLogData(allPeersData, 'allPeersData.json')
    cmd = ''
    while cmd != '<exit>':
        peer_request = decryptChannel(peerSock.recv(1024))
        cmd = peer_request['cmd']
        if not cmd:
            break
        cmdEntered = cmd.split()

        if cmdEntered[0] == 'create':
            response = {}
            if cmdEntered[1] in allPeersData:
                response = createErrorObj(400,'{0} already exists in the system'.format(cmdEntered[1]))
            else:
                allPeersData[cmdEntered[1]] = {
                    'owner': peerId,
                    'permissions': cmdEntered[2],
                    'replicatedPeers': replicationHandler(),
                    'encKey': str(Fernet.generate_key()),
                    'isCurrentlyOpen': 'false',
                    'deleted': 'false',
                    'isDirectory': 'false'
                }
                writeLogData(allPeersData, 'allPeersData.json')
                for key, values in activePeers.items():
                    if key != peerId:
                        response[key] = {
                            'IP': values['IP'],
                            'PORT': values['PORT']
                        }
            peerSock.send(encryptChannel(response))

        elif cmdEntered[0] == 'read':
            response = {}
            if cmdEntered[1] not in allPeersData:
                response = createErrorObj(404,'file: {0} not found!'.format(cmdEntered[1]))
            else:
                print(cmdEntered)
                # fetch file allFilesData
                allFilesData = allPeersData[cmdEntered[1]]
                print(allFilesData)
                if 'deleted' in allFilesData and allFilesData['deleted'] == 'true':
                    if allFilesData['owner'] == peerId:
                        response = createErrorObj(401,'file: {0}  does not exists.Please run `restore filename` command to restore the file'.format(cmdEntered[1]))
                    else:
                        response = createErrorObj(404,'file: {0} not found!'.format(cmdEntered[1]))
                elif allFilesData['isDirectory'] == 'true':
                    response = createErrorObj(400,'file: {0} is a directory'.format(cmdEntered[1]))
                elif allFilesData['isCurrentlyOpen'] == 'true':
                    response = createErrorObj(400,'file: {0} is being accessed currently'.format(cmdEntered[1]))
                else:
                    # unless the file is access restricted(3), when only the owner can access
                    isAccessible = (peerId != allFilesData['owner']) and (int(allFilesData['permissions']) == 3)
                    if not isAccessible:
                        response['encKey'] = allFilesData['encKey']
                        replicatedPeers = allFilesData['replicatedPeers']
                        response['repPeerInfo'] = {}
                        for replicated_peer in replicatedPeers:
                            response['repPeerInfo'][replicated_peer] = activePeers[replicated_peer]
                    else:
                        response = createErrorObj(401,'{0} does not have access to {1}'.format(peerId, cmdEntered[1]))
            peerSock.send(encryptChannel(response))

        elif cmdEntered[0] == 'write':
            response = {}
            if cmdEntered[1] not in allPeersData:
                response = createErrorObj(404,'file: {0} not found!'.format(cmdEntered[1]))
                peerSock.send(encryptChannel(response))
                pRes = decryptChannel(peerSock.recv(1024))
                continue
            else:
                allFilesData = allPeersData[cmdEntered[1]]
                isAccessible = peerId == allFilesData['owner'] or int(allFilesData['permissions']) == 1

                if allPeersData[cmdEntered[1]]['deleted'] == 'true':
                    response = createErrorObj(404,'file: {0} not found!'.format(cmdEntered[1]))
                elif allFilesData['isDirectory'] == 'true':
                    response = createErrorObj(400,'file: {0} is a directory'.format(cmdEntered[1]))
                elif isAccessible:
                    response['encKey'] = allFilesData['encKey']
                    response['repPeerInfo'] = {}
                    response['encrypted_file_name'] = cmdEntered[1]
                    replicatedPeers = allFilesData['replicatedPeers']
                    for replicated_peer in replicatedPeers:
                        if replicated_peer != peerId:
                            response['repPeerInfo'][replicated_peer] = activePeers[replicated_peer]
                    allPeersData[cmdEntered[1]]['isCurrentlyOpen'] = 'true'
                else:
                    response = createErrorObj(401,'{0} does not have permission to access {1}'.format(peerId, cmdEntered[1]))
                writeLogData(allPeersData, 'allPeersData.json')
                peerSock.send(encryptChannel(response))
                pRes = decryptChannel(peerSock.recv(1024))
                if pRes['message'] == 'SUCCESS':
                    allPeersData[cmdEntered[1]]['isCurrentlyOpen'] = 'false'
                writeLogData(allPeersData, 'allPeersData.json')

        elif cmdEntered[0] == 'delete':
            response = {}
            if cmdEntered[1] not in allPeersData:
                response = createErrorObj(404,'file: {0} not found!'.format(cmdEntered[1]))
            else:
                allFilesData = allPeersData[cmdEntered[1]]
                isAccessible = peerId == allFilesData['owner']
                if allFilesData['isCurrentlyOpen'] == 'true':
                    response = createErrorObj(400,'file: {0} is already in use.'.format(cmdEntered[1]))
                elif not isAccessible:
                    response = createErrorObj(401,'{0} does not have access to delete {1}'.format(peerId, cmdEntered[1]))
                elif allFilesData['deleted'] == 'true':
                    response = createErrorObj(400,'file: {0} is already deleted'.format(cmdEntered[1]))
                else:
                    allPeersData[cmdEntered[1]]['deleted'] = 'true'
                    request = encryptChannel({
                        'cmd': cmd
                    })

                    peersInWhichFileDeleted = []
                    for peer in allFilesData['replicatedPeers']:
                        if peer != allFilesData['owner']:
                            peerData = activePeers[peer]
                            peerIP = peerData['IP']
                            peerPort = peerData['PORT']
                            print('Connecting to {0} at IP:{1} on port:{2}'.format(peer, peerIP, peerPort))
                            repPSock = socket(AF_INET, SOCK_STREAM)
                            repPSock.connect((peerIP, int(peerPort)))
                            repPSock.send(request)
                            repPResponse = decryptChannel(repPSock.recv(1024))
                            if 'error' in repPResponse:
                                print(repPResponse['message'])
                            else:
                                peersInWhichFileDeleted.append(peer)
                                print(repPResponse['message'])
                            print()
                    response = {
                        'message': '{0} deleted successfully in these peers: {1}.'.format(cmdEntered[1], peersInWhichFileDeleted)
                    }
                    for peer in peersInWhichFileDeleted:
                        allPeersData[cmdEntered[1]]['replicatedPeers'].remove(peer)
                    writeLogData(allPeersData, 'allPeersData.json')
            peerSock.send(encryptChannel(response))

        elif cmdEntered[0] == 'ls':
            response = {
                'message': []
            }
            for fileName, attr in allPeersData.items():
                data = ''

                if (attr['permissions'] == "3" or attr['deleted'] == 'true') and attr['owner'] != peerId:
                    continue

                file_name = fileName

                data += 'directory' if attr['isDirectory'] == 'true' else '-'
                data += ' '

                if attr['permissions'] == '1':
                    data += 'read-write'
                elif attr['permissions'] == '2':
                    data += 'read-write' if attr['owner'] == peerId else 'read'
                else:
                    data += 'private'
                data += ' '

                data += file_name
                response['message'].append(data)
            print(response)
            peerSock.send(encryptChannel(response))

        elif cmdEntered[0] == 'restore':
            response = {}
            if cmdEntered[1] not in allPeersData:
                response = createErrorObj(404,'file: {0} not found!'.format(cmdEntered[1]))
            else:
                allFilesData = allPeersData[cmdEntered[1]]
                if 'deleted' in allFilesData and allFilesData['deleted'] != "true":
                    response = createErrorObj(400,'file: {0} not found!'.format(cmdEntered[1]))
                elif allFilesData['owner'] != peerId:
                    response = createErrorObj(403,'file: {0} restored.'.format(cmdEntered[1]))
                else:
                    response['peers_to_replicate'] = []
                    for peer in replicationHandler():
                        allPeersData[cmdEntered[1]]['replicatedPeers'].append(peer)
                        response['peers_to_replicate'].append({
                            "IP": activePeers[peer]["IP"],
                            "PORT": activePeers[peer]["PORT"]
                        })
                    response['message'] = 'REP_SUCCESS'
                allPeersData[cmdEntered[1]]['deleted'] = 'false'
                peerSock.send(encryptChannel(response))
                writeLogData(allPeersData, 'allPeersData.json')

        elif cmdEntered[0] == 'mkdir':
            response = {}
            if cmdEntered[1] in allPeersData:
                response = createErrorObj(400,'{0} already exists in the system'.format(cmdEntered[1]))
            else:
                allPeersData[cmdEntered[1]] = {
                    'owner': peerId,
                    'permissions': cmdEntered[2],
                    'replicatedPeers': [process for process in activePeers.keys()],
                    'deleted': 'false',
                    'encKey': str(Fernet.generate_key()),
                    'isDirectory': 'true'
                }
                writeLogData(allPeersData, 'allPeersData.json')
                for key, values in activePeers.items():
                    if key != peerId:
                        response[key] = {
                            'IP': values['IP'],
                            'PORT': values['PORT']
                        }
            peerSock.send(encryptChannel(response))

        elif cmdEntered[0] == 'rmdir':
            response = {}
            if cmdEntered[1] not in allPeersData or allPeersData[cmdEntered[1]]['deleted'] == 'true':
                response = createErrorObj(404,'folder: {0} not found!'.format(cmdEntered[1]))
            else:
                allPeersData[cmdEntered[1]]['deleted'] = 'true'
                writeLogData(allPeersData, 'allPeersData.json')
                for key, values in activePeers.items():
                    if key != peerId:
                        response[key] = {
                            'IP': values['IP'],
                            'PORT': values['PORT']
                        }
            peerSock.send(encryptChannel(response))

    print(peerId, 'disconnected from the Server!')
    activePeers.pop(peerId, None)
    writeLogData(activePeers, 'activePeers.json')


def main():

    peerRegisterThread = Thread(target = registeringPeer)
    peerRegisterThread.start()
    
    while True:
        peerSock, sockAddr = serverSock.accept()
        peerHandlerThread = Thread(target = peerRequestHandler, args=(peerSock,sockAddr))
        peerHandlerThread.daemon = True
        peerHandlerThread.start()

if __name__ == '__main__':
    main()

serverSock.close()