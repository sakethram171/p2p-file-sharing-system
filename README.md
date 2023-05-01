**GOAL**:

    This project aims to build a distributed file system using peer-to-peer communication on a centralized directory architecture using the AES encryption algorithm.
    
**Architecture**:

    Centralized Server:
        The Centralized Server(CS) is similar to the directory service. It stores the information of all the connected peers and their IP addresses. 
        It maintains a list of files each peer has made available to share. Each peer would first connect to the Centralized Server for any query. 
        This Centralized server with all the information about the files and the peers will respond to the query with the IP addresses of all other 
        peers with the requested file. The CS will authenticate the read and write permissions for the file and then responds to the peer : 
                                        1. CS will respond with IP addresses if the requesting peer has all the permissions to perform operations on the file.
                                        2. Else, CS will deny the request by saying “Access denied to the requested file” message.
    Peer: 
        Each peer will first connect with the Centralized Server(CS). Every file request(read/write)  will be sent to the CS first to obtain the list 
        of IPs of the other peers. If CS responds with an IP, the requesting peer will connect to that IP to perform the operations on the file.	


