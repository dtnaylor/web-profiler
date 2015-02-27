#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <arpa/inet.h>
#include <errno.h>
#include <time.h>

#define REQUEST_SIZE 4096
#define RESPONSE_BUF_SIZE 500*1024

int main(int argc, char* argv[])
{
	/*************** PARSE ARGUMENTS ***************/
    if (argc != 4)
    {
        fprintf(stderr, "usage: %s protocol host path\n",argv[0]);
        return EXIT_FAILURE;
    }
	char *protocol = argv[1];
	char *host = argv[2];
	char *path = argv[3];

	/*************** PREPARE REQUEST ***************/
	char request[REQUEST_SIZE];
	snprintf(request, REQUEST_SIZE, "GET %s HTTP/1.1\r\nHost: %s\r\n\r\n",
		path, host);

	printf("Request (len %lu):\n%s\n", strlen(request), request);

        
	/*************** RESOLVE DNS ADDR ***************/
    int status, sock;
    struct addrinfo hints;
	memset(&hints, 0, sizeof(struct addrinfo));
    struct addrinfo *servinfo;
    hints.ai_family = AF_INET;  // IPv4
    hints.ai_socktype = SOCK_STREAM;  // TCP stream sockets
    hints.ai_flags = AI_PASSIVE;  // fill in my IP for me
    
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);

    if ((status = getaddrinfo(host, protocol, &hints, &servinfo)) != 0) 
    {
        fprintf(stderr, "getaddrinfo error: %s \n", gai_strerror(status));
        return EXIT_FAILURE;
    }

	struct sockaddr_in *addr;
    addr = (struct sockaddr_in *)servinfo->ai_addr; 
	printf("Server addr: %s:%d\n", inet_ntoa((struct in_addr)addr->sin_addr),
		ntohs(addr->sin_port));


	/*************** CONNECT ***************/
    if((sock = socket(servinfo->ai_family, servinfo->ai_socktype, servinfo->ai_protocol)) == -1)
    {
        fprintf(stderr, "Socket failed");
        return EXIT_FAILURE;
    }
    
    if (connect (sock, servinfo->ai_addr, servinfo->ai_addrlen) == -1)
    {
        fprintf(stderr, "Error connecting: %s\n", strerror(errno));
        return EXIT_FAILURE;
    }
        

	/*************** SEND REQUEST ***************/
    send(sock, request, strlen(request), 0);

	/* TFO connect and send out some data */
    //fprintf(stdout, "[TFO]  Sending %s", request);
	//sendto(sock, request, strlen(request), MSG_FASTOPEN, servinfo->ai_addr, servinfo->ai_addrlen);


	/*************** RECEIVE RESPONSE ***************/
    char buf[RESPONSE_BUF_SIZE];
    int total_bytes_received = 0;
	int bytes_received = 0;  // during last recv() call
	int header_length = 0;
	int content_length = 0;

	do {
		bytes_received = recv(sock, &buf[total_bytes_received],
			RESPONSE_BUF_SIZE-total_bytes_received, 0);
		total_bytes_received += bytes_received;
		if (bytes_received == -1)
		{
			fprintf(stderr, "Error receiving: %s\n", strerror(errno));
			return EXIT_FAILURE;
		}

		// If we still don't know content length, look for Content-Length hdr
		if (content_length == 0) {
			char *length_header_start = strstr(buf, "Content-Length");
			if (length_header_start) {
				char *length_header_end = strstr(length_header_start, "\r\n");
				int num_digits = length_header_end-length_header_start - 16;

				char length_str[20];
				memcpy(length_str, length_header_start+16, num_digits);
				length_str[num_digits] = '\0';
				content_length = atoi(length_str);
				printf("length: %d\n", content_length);
			}
		}

		// If we still don't know header length, look for \r\n\r\n
		if (header_length == 0) {
			char *return_start = strstr(buf, "\r\n\r\n");
			if (return_start) {
				header_length = (return_start - buf) + 4;
				printf("Header length: %d\n", header_length);
			}
		}
	} while (bytes_received > 0 && total_bytes_received < header_length + content_length);

    clock_gettime(CLOCK_MONOTONIC, &end);
    double seconds_elapsed = end.tv_sec - start.tv_sec + (end.tv_nsec - start.tv_nsec) / 1000000000.0;

	buf[total_bytes_received] = '\0';
	//fprintf(stdout, "Received %s", buf);

    freeaddrinfo(servinfo);
    close(sock);    


	/*************** RETURN STATUS ***************/
    // return info to python wrapper by printing to last line of stdout
    printf("tcp_fast_open_used=0");
    printf(";time_seconds=%f\n", seconds_elapsed);

    return EXIT_SUCCESS;
}
