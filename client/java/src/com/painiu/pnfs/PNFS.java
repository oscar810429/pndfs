/*
 * @(#)PNFS.java Nov 12, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Properties;

import org.apache.commons.httpclient.HttpClient;
import org.apache.commons.httpclient.HttpException;
import org.apache.commons.httpclient.HttpMethod;
import org.apache.commons.httpclient.HttpStatus;
import org.apache.commons.httpclient.MultiThreadedHttpConnectionManager;
import org.apache.commons.httpclient.cookie.CookiePolicy;
import org.apache.commons.httpclient.methods.DeleteMethod;
import org.apache.commons.httpclient.methods.GetMethod;
import org.apache.commons.httpclient.methods.InputStreamRequestEntity;
import org.apache.commons.httpclient.methods.PutMethod;
import org.apache.commons.httpclient.params.HttpClientParams;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

import com.painiu.pnfs.Request.Command;

/**
 * <p>
 * <a href="YPFS.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public class PNFS {
	//~ Static fields/initializers =============================================

	private static final Log log = LogFactory.getLog(PNFS.class);
	
	private static final String DEFAULT_SETTINGS = "pnfs.properties";
	
	public static final String TEXT_ENCODING = "UTF-8";
	
	//~ Instance fields ========================================================

	private static boolean initialized = false;
	private static SockIOPool pool;
	private static HttpClient httpClient;
	
	//~ Constructors ===========================================================

	//~ Methods ================================================================
	
	public synchronized static void initialize(Properties props) {
		if (props == null) {
			props = new Properties();
			
			try {
				props.load(Thread.currentThread().getContextClassLoader().getResourceAsStream(DEFAULT_SETTINGS));
			} catch (IOException e) {
				log.error("IOException occurred while loading file " + DEFAULT_SETTINGS);
				
				throw new RuntimeException("error loading configuration file", e);
			}
		}
		
		String[] servers = props.getProperty("servers", "").split("\\s");
		int initialConnections  = Integer.parseInt(props.getProperty("initialConnections", "3"));
		int minSpareConnections = Integer.parseInt(props.getProperty("minSpareConnctions", "5"));
		int maxSpareConnections = Integer.parseInt(props.getProperty("maxSpareConnections", "50"));
		long maxIdleTime        = Long.parseLong(props.getProperty("maxIdleTime", "1800000"));   // 30 minutes
		long maxBusyTime        = Long.parseLong(props.getProperty("maxBusyTime", "300000"));    // 5 minutes
		long maintThreadSleep   = Long.parseLong(props.getProperty("maintThreadSleep", "10000")); // 10 seconds
		int	socketTimeOut       = Integer.parseInt(props.getProperty("socketTimeOut", "3000")); 	// 3 seconds to block on reads
		
		int	socketConnectTO     = 1000 * 3;			// 3 seconds to block on initial connections.  If 0, then will use blocking connect (default)
		boolean failover        = false;			// turn off auto-failover in event of server down	
		boolean nagleAlg        = false;			// turn off Nagle's algorithm on all sockets in pool	
		boolean aliveCheck      = false;			// enable health check of socket on checkout

		pool = SockIOPool.getInstance();
		pool.setServers(servers);

		if (props.containsKey("weights")) {
			String[] weightsStr = props.getProperty("weights").split(",");
			Integer[] weights = new Integer[weightsStr.length];
			for (int i = 0; i < weightsStr.length; i++) {
				weights[i] = new Integer(weightsStr[i]);
			}
			pool.setWeights(weights);
		}
		
		pool.setSocketConnectTO(socketConnectTO);
		pool.setInitConn(initialConnections);
		pool.setMinConn(minSpareConnections);
		pool.setMaxConn(maxSpareConnections);
		pool.setMaxIdle(maxIdleTime);
		pool.setMaxBusyTime(maxBusyTime);
		pool.setMaintSleep(maintThreadSleep);
		pool.setSocketTO(socketTimeOut);
		pool.setFailover(failover);
		pool.setNagle(nagleAlg);
		pool.setAliveCheck(aliveCheck);

		pool.initialize();
		
		HttpClientParams params = new HttpClientParams();
		params.setCookiePolicy(CookiePolicy.IGNORE_COOKIES);
		params.setConnectionManagerClass(MultiThreadedHttpConnectionManager.class);
		httpClient = new HttpClient(params);
		
		initialized = true;
	}
	
	public static Path httpPutFile(java.io.File file, List<Path> dists) {
		for (Path path : dists) {
			if (log.isDebugEnabled()) {
				log.debug("Sending file to: " + path.getPath());
			}
			
			PutMethod put = new PutMethod(path.getPath());
			InputStream in = null;
			
			try {
				in = new FileInputStream(file);
				put.setRequestEntity(new InputStreamRequestEntity(in));
				
				int statusCode = httpClient.executeMethod(put);
				
				if (statusCode == HttpStatus.SC_OK || statusCode == HttpStatus.SC_CREATED) {
					return path;
				}
			} catch (HttpException e) {
				log.error("HttpException occurred while sending file: ", e);
			} catch (IOException e) {
				log.error("IOException occurred while sending file: ", e);
			} finally {
				put.releaseConnection();
				if (in != null) {
					try {
						in.close();
					} catch (IOException e) {}
				}
			}
		}
		
		return null;
	}
	
	public static void httpDeleteFile(String uri) {
		if (log.isDebugEnabled()) {
			log.debug("Deleting file: " + uri);
		}
		
		DeleteMethod del = new DeleteMethod(uri);
		try {
			httpClient.executeMethod(del);
		} catch (HttpException e) {
			log.error("HttpException occurred while sending file", e);
		} catch (IOException e) {
			log.error("IOException occurred while sending file", e);
		} finally {
			del.releaseConnection();
		}
	}
	
	public static InputStream httpGetFile(List<String> urls) {
		for (String url : urls) {
			if (log.isDebugEnabled()) {
				log.debug("Getting file: " + url);
			}
			
			GetMethod get = new GetMethod(url);
			
			try {
				int statusCode = httpClient.executeMethod(get);
				if (statusCode == HttpStatus.SC_OK) {
					return new HttpInputStream(get);
				}
			} catch (IOException e) {
				log.error("IOException occurred while getting file: " + url);
				get.releaseConnection();
			}
		}
		
		return null;
	}
	
	public static void delete(File file) throws PNFSException {
		request(Command.DELETE, file);
	}
	
	public static void enable(File file) throws PNFSException {
		request(Command.ENABLE, file);
	}
	
	public static void disable(File file) throws PNFSException {
		request(Command.DISABLE, file);
	}
	
	public static void enableUser(String username) throws PNFSException {
		Request request = new Request(Command.ENABLE);
		request.addArg("class", "user");
		request.addArg("username", username);
		request(request, 5);
	}
	
	public static void disableUser(String username) throws PNFSException {
		Request request = new Request(Command.DISABLE);
		request.addArg("class", "user");
		request.addArg("username", username);
		request(request, 5);
	}
	
	public static void setUserLevel(String username, int level) throws PNFSException {
		Request request = new Request(Command.SET_LEVEL);
		request.addArg("class", "user");
		request.addArg("username", username);
		request.addArg("level", String.valueOf(level));
		request(request, 5);
	}
	
	/**
	 * Set user max flow, the unit is megabit/M
	 * 
	 * @param username
	 * @param maxFlow
	 * @throws PNFSException
	 */
	public static void setUserMaxFlow(String username, long maxFlow) throws PNFSException {
		Request request = new Request(Command.SET_MAX_FLOW);
		request.addArg("class", "user");
		request.addArg("username", username);
		request.addArg("max_flow", String.valueOf(maxFlow));
		request(request, 5);
	}
	
	/**
	 * set vip type:<br/>
	 * <li> 0: None VIP
	 * <li> 1: Normal VIP
	 * <li> 2: Commerical VIP
	 * 
	 * @param username
	 * @param vip
	 * @throws PNFSException
	 */
	public static void setUserVip(String username, int vip) throws PNFSException {
		if (vip < 0 || vip > 2) {
			throw new IllegalArgumentException("Invliad vip value");
		}
		Request request = new Request(Command.SET_VIP);
		request.addArg("class", "user");
		request.addArg("username", username);
		request.addArg("vip", String.valueOf(vip));
		request(request, 5);
	}
	
	public static void setPhotoCustomSize(String username, String filename, int size) throws PNFSException {
		Request request = new Request(Command.CUSTOM_SIZE);
		request.addArg("class", "photo");
		request.addArg("username", username);
		request.addArg("filename", filename);
		request.addArg("size", String.valueOf(size));
		request(request, 5);
	}
	
	/*public static List<UserFlow> getUserFlows(String username) throws YPFSException {
		Request request = new Request(Command.GET_FLOWS);
		request.addArg("class", "user");
		request.addArg("username", username);
		Response rsp = request(request, 5);
		
		List<UserFlow> flows = new ArrayList<UserFlow>(rsp.getArgs().size());
		for (Iterator<Map.Entry<String, String>> i = rsp.getArgs().entrySet().iterator(); i.hasNext();) {
			Map.Entry<String, String> entry = i.next();
			String month = entry.getKey();
			if (month.startsWith("m_")) {
				month = month.substring(2);
				try {
					long flow = Long.parseLong(entry.getValue());
					flows.add(new UserFlow(month, flow));
				} catch (NumberFormatException e) {}
			}
		}
		
		Collections.sort(flows);
		
		return flows;
	}*/
	
	
	private static Request createRequest(Command cmd, File file) {
		Request request = new Request(cmd);
		request.addArg("class", file.getType());
		request.addArg("username", file.getUsername());
		request.addArg("filename", file.getFilename());
		return request;
	}
	
	public static Response request(Command cmd, File file) throws PNFSException {
		return request(createRequest(cmd, file));
	}
	
	public static Response request(Request request) throws PNFSException {
		return request(request, 5);
	}
	
	public static Response request(Request request, int retry) throws PNFSException {
		if (!initialized) {
			throw new IllegalStateException("YPFS is not initialized");
		}
		
		SockIOPool.SockIO sock = pool.getSock();

		// return false if unable to get SockIO obj
		if (sock == null) {
			throw new PNFSException("unable to connect to ypfs hosts");
		}

		// build command
		String command = request.encode();

		if (log.isDebugEnabled()) {
			log.debug("REQUEST[" + sock.getHost() + "]: " + command);
		}
		
		String rspString = null;

		try {
			sock.write(command.getBytes());
			sock.flush();
			
			// if we get appropriate response back, then we return true
			rspString = sock.readLine();
			System.out.println(rspString);
			
		} catch (IOException e) {
			// exception thrown
			log.error("++++ exception thrown while writing bytes to server on delete");
			log.error(e.getMessage(), e);

			try {
				sock.trueClose();
			} catch (IOException ioe) {
				log.error("++++ failed to close socket : " + sock.toString());
			}

			sock = null;
			
			return retry(request, retry, e.getMessage(), null);
		}

		sock.close();
		
		if (log.isDebugEnabled()) {
			log.debug("RESPONSE[" + sock.getHost() + "]: " + rspString);
		}
		
		Response response = Response.decode(rspString);
		
		if (response.getState() == Response.State.ERR) {
			throw new PNFSException(response.getCode(), response.getMessage());
		}
		
		return response;
	}
	
	private static Response retry(Request request, int retry, String failMsg, PNFSException cause) throws PNFSException {
		if (retry > 0) {
			if (log.isWarnEnabled()) {
				log.warn("request[" + request.getCommand() + "] failed: " + failMsg + "; retry...");
			}
			return request(request, retry - 1);
		}
		if (cause != null) {
			throw cause;
		}
		throw new PNFSException(null, failMsg);
	}
	
	static class HttpInputStream extends InputStream {
		private InputStream stream;
		private HttpMethod http;
		
		public HttpInputStream(HttpMethod http) throws IOException {
			this.http = http;
			this.stream = http.getResponseBodyAsStream();
		}
		
		/*
		 * @see java.io.InputStream#close()
		 */
		@Override
		public void close() throws IOException {
			stream.close();
			http.releaseConnection();
		}
		
		/*
		 * @see java.io.InputStream#read()
		 */
		@Override
		public int read() throws IOException {
			return stream.read();
		}
		
		/*
		 * @see java.io.InputStream#read(byte[])
		 */
		@Override
		public int read(byte[] b) throws IOException {
			return stream.read(b);
		}
		
		/*
		 * @see java.io.InputStream#read(byte[], int, int)
		 */
		@Override
		public int read(byte[] b, int off, int len) throws IOException {
			return stream.read(b, off, len);
		}
		
		/*
		 * @see java.io.InputStream#skip(long)
		 */
		@Override
		public long skip(long n) throws IOException {
			return stream.skip(n);
		}
		
		/*
		 * @see java.io.InputStream#available()
		 */
		@Override
		public int available() throws IOException {
			return stream.available();
		}
	}
	
	public static class Path {
		private String fid;
		private String devid;
		private String path;
		
		public Path(String fid, String devid, String path) {
			this.fid = fid;
			this.devid = devid;
			this.path = path;
		}
		
		/**
		 * @return the fid
		 */
		public String getFid() {
			return fid;
		}
		
		/**
		 * @return the devid
		 */
		public String getDevid() {
			return devid;
		}
		
		/**
		 * @return the path
		 */
		public String getPath() {
			return path;
		}
	}
}
