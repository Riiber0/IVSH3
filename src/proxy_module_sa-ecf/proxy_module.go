package main

import "C"

import (
	"bytes"
	"crypto/tls"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"
	"fmt"
	"net"

	"golang.org/x/net/http2"

	"github.com/lucas-clemente/quic-go"
	"github.com/lucas-clemente/quic-go/h2quic"
)

func main() {}

const (
	// Prefix for PROXY specific messages
	logTag = "PROXY MODULE:"
)

var (
	/* Specify if the single connection between the proxy and
	 * the remote host is kept open between requests.
	 */
	keepAlive = true

	// Use QUIC instead of tcp
	useQUIC bool
	// Activate multipath, when QUIC is used
	useMP bool
	// Activate multstream
	useMS bool
	
	/* Global HTTP/2 Client:
	* Only one is used for all incoming connections, for accessing
	* the transportion behaviour over a dedicated connection.
	*/
	hclient *http.Client
	h2client *h2quic.Client
	roundTripper *h2quic.RoundTripper

	// Specifiy wether the download rate should be logged periodically to file.
	loggerDeployed bool
	logFile *os.File
	logStart int64
	logTicker *time.Ticker
	logStopChannel chan struct{}

	logLastTS int64
	recvBytes uint64
	lastRecvBytes uint64
)

//export ClientSetup
func ClientSetup(usequic, mp, ms, keepalive bool, scheduler string, cc string) {
	useQUIC = usequic
	useMP = mp
	keepAlive = keepalive
	//quic.SetSchedulerAlgorithm(scheduler)
	//quic.LogPayload = false
	//quic.SetCongestionControl(cc)
	useMS = ms
}

//export CloseConnection
func CloseConnection() {
	if hclient != nil {
		hclient.CloseIdleConnections()
		hclient = nil
	} else if h2client!= nil {
		h2client = nil
	}
	if roundTripper != nil {
		roundTripper.Close()
	}
}

func listLocalIPs() {
	fmt.Println("IPs locais visíveis pela aplicação:")
	ifaces, err := net.Interfaces()
	if err != nil {
		log.Fatalf("Erro ao listar interfaces: %v", err)
	}

	for _, iface := range ifaces {
		// Ignora interfaces inativas
		if iface.Flags&net.FlagUp == 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, addr := range addrs {
			fmt.Printf("- [%s] %s\n", iface.Name, addr.String())
		}
	}
}

//export DownloadSegment
func DownloadSegment(segmentURL string) int {

	if hclient == nil {
		createRemoteClient()
	}

	// Send request to the remote host
	rsp, err := hclient.Get(segmentURL)
	if err != nil {
		log.Println(logTag, "error : ", err)
		return -1
	}

	// Synchronous (blocking) stream forwarding to buffer.
	// Ends on EOF or error.
	body := &bytes.Buffer{}
	_, err = io.Copy(body, rsp.Body)
	if err != nil {
		log.Println(logTag, "error : ", err)
		return -1
	}
	rsp.Body.Close()
	recvBytes += uint64(body.Len())

	return body.Len()
}

//export DownloadSegmentPriority
func DownloadSegmentPriority(segmentURL string, segmentPriority uint8) int {

	if h2client == nil{
		createRemoteClient()
	}

	// Set stream priority
	priority := &http2.PriorityParam{
		Weight:    segmentPriority,
		StreamDep: 0x0,
		Exclusive: false,
	}


	// Send request to the remote host
	rsp, err := h2client.Get(segmentURL, priority)
	if err != nil {
		fmt.Printf("%s error: %s",logTag, err)
		return -1
	}

	// Synchronous (blocking) stream forwarding to buffer.
	// Ends on EOF or error.
	body := &bytes.Buffer{}
	_, err = io.Copy(body, rsp.Body)
	if err != nil {
		fmt.Printf("%s error: %s",logTag, err)
		return -1
	}
	rsp.Body.Close()
	recvBytes += uint64(body.Len())

	return body.Len()
}

// Create a HTTP/2.0 client with different transport protocols
func createRemoteClient() {

	// Accept any offered certificate chain
	tlsConfig := &tls.Config{InsecureSkipVerify: true}

	if useQUIC {
		if useMS{
			// Use a HTTP/2.0 connection via QUIC, sa-ecf API
			roundTripper = &h2quic.RoundTripper{
				TLSClientConfig: tlsConfig,
				QuicConfig: &quic.Config{CreatePaths: useMP,
							IdleTimeout: 20 * time.Second,
							KeepAlive: true,
							HandshakeTimeout: 20 * time.Second,},
			}

			h2client = &h2quic.Client{
				Timeout: time.Second *10,
				Transport: *roundTripper,
			}


		} else {
			// Use a HTTP/2.0 connection via QUIC, default API
			roundTripper = &h2quic.RoundTripper{
				TLSClientConfig: tlsConfig,
				QuicConfig: &quic.Config{CreatePaths: useMP,
							IdleTimeout: 20 * time.Second,
							KeepAlive: true,
							HandshakeTimeout: 20 * time.Second,},
			}

			hclient = &http.Client{
				Timeout: time.Second * 10,
				Transport: roundTripper,
			}
		}

		fmt.Printf("%s created http2 QUIC client (MP: %t, %t)\n", logTag, useMP, useMS)
	} else {
		// Use a HTTP/2.0 connection via TLS
		hclient = &http.Client{}

		// configure client to use http2
		transport := &http.Transport{
			TLSClientConfig: tlsConfig,
		}
		err := http2.ConfigureTransport(transport)
		if err != nil {
			log.Printf("%s ConfigureTransport http2 %v\n", logTag, err)
		}
		hclient.Transport = transport

		log.Printf("%s created http2 TLS client\n", logTag)
	}
}

//export StartLogging
func StartLogging(period uint) {

	os.Setenv("QUIC_GO_LOG_LEVEL", "INFO")
	/*
	if logTicker == nil {
		logTicker = time.NewTicker(time.Duration(period) * time.Millisecond)
		logStopChannel = make(chan struct{})

		go logReceivings(logTicker, logStopChannel)
	}
	*/
	f, err := os.Create("/shared/quic_log.txt")
	defer f.Close()
	if err != nil {
		panic(err)
	}
	log.SetOutput(f)
}

//export StopLogging
func StopLogging() {

	if logStopChannel != nil {
		logStopChannel <- struct{}{}
	}
}

// Periodic logging routine
func logReceivings(ticker *time.Ticker, stopChannel chan struct{}) {

	for {
		select {
		case <-ticker.C:
			// Received logging tick, perform logging routine
			if logFile == nil {
				logStart = time.Now().UnixNano()
				logLastTS = logStart

				// Open log file
				filename := "Client" + "_recv.log"
				var err error
				logFile, err = os.OpenFile(filename, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
				if err != nil {
					return
				}
			}

			// Time measuring
			now := time.Now().UnixNano()
			elapsed := float64((now - logLastTS) / 1e6)
			logLastTS = now
			
			// Only read recvBytes variable once, since it is thread shared
			recvBytesCopy := recvBytes
			// Download rate over the last period in KBit/s
			sentDelta := recvBytesCopy - lastRecvBytes
			lastRecvBytes = recvBytesCopy
			sendRate := float64(sentDelta) * 8.0 / elapsed
			
			// Transform absolute to relative [ms] timestamp string
			timestring := strconv.FormatFloat(float64((now - logStart) / 1e6), 'f', -1, 64)
			logLine := timestring + ";" + strconv.FormatFloat(sendRate, 'g', -1, 64) + "\n"
			logFile.WriteString(logLine)
		case <-stopChannel:
			// Stop loggine
			ticker.Stop()
			return
		}
	}
}
