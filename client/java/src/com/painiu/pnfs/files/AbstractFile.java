/*
 * @(#)AbstractFile.java Nov 8, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs.files;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.painiu.pnfs.File;
import com.painiu.pnfs.Request;
import com.painiu.pnfs.Response;
import com.painiu.pnfs.PNFS;
import com.painiu.pnfs.PNFSException;
import com.painiu.pnfs.Request.Command;
import com.painiu.pnfs.PNFS.Path;

/**
 * <p>
 * <a href="AbstractFile.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public abstract class AbstractFile implements File {
	//~ Static fields/initializers =============================================

	//~ Instance fields ========================================================

	protected String username;
	protected java.io.File file;
	
	protected String contentType;
	
	protected String filename; // this is generated by YPFS
	
	//~ Constructors ===========================================================
	
	public AbstractFile(String username, String filename) {
		this.username = username;
		this.filename = filename;
	}
	
	public AbstractFile(String username, java.io.File file, String contentType) {
		if (!file.exists() || !file.isFile()) {
			throw new IllegalArgumentException("File " + file.getAbsolutePath() + " is not a exists, or is not a file.");
		}
		this.username = username;
		this.file = file;
		this.contentType = contentType;
	}
	
	//~ Methods ================================================================

	/*
	 * @see com.painiu.pnfs.File#store()
	 */
	public void store() throws PNFSException {
		Response rsp = createOpen();
		
		List<Path> paths = parsePaths(rsp);

		Path path = PNFS.httpPutFile(file, paths);
		
		if (path == null) {
			throw new PNFSException("Failed to send file to YPFS storage node");
		}
		
		try {
			createClose(path);
		} catch (PNFSException e) {
			// rollback
			PNFS.httpDeleteFile(path.getPath());
			throw e;
		}
	}
	
	protected Response createOpen() {
		Response rsp = PNFS.request(Command.CREATE_OPEN, this);
		setFilename(rsp.getArgs().get("filename"));
		return rsp;
	}
	
	protected Response createClose(Path path) {
		Request request = createCloseRequest(path);
		return PNFS.request(request, 2);
	}
	
	protected Request createCloseRequest(Path path) {
		Request request = new Request(Command.CREATE_CLOSE);
		request.addArg("class", getType());
		request.addArg("filename", getFilename());
		request.addArg("size", String.valueOf(getFile().length()));
		request.addArg("fid", path.getFid());
		request.addArg("devid", path.getDevid());
		request.addArg("path", path.getPath());
		if (username != null) {
			request.addArg("username", getUsername());
		}
		if (contentType != null) {
			request.addArg("content_type", getContentType());
		}
		return request;
	}
	
	protected List<Path> parsePaths(Response response) {
		Map<String, String> args = response.getArgs();

		String fid = args.get("fid");
		List<Path> dists = null;
		
		if (args.containsKey("dev_count")) {
			int count = Integer.parseInt(args.get("dev_count"));
			
			dists = new ArrayList<Path>(count);
			
			for (int i = 1; i <= count; i++) {
				dists.add(new Path(fid, args.get("devid_" + i), args.get("path_" + i)));
			}
		} else {
			dists = new ArrayList<Path>(1);
			dists.add(new Path(fid, args.get("devid"), args.get("path")));
		}
		return dists;
	}
	
	/*
	 * @see com.painiu.pnfs.File#getInputStream()
	 */
	public InputStream getInputStream() throws PNFSException, IOException {
		InputStream in = PNFS.httpGetFile(getPaths());
		if (in == null) {
			throw new IOException("Can not read remote file");
		}
		return in;
	}
	
	protected List<String> getPaths() throws PNFSException {
		Request request = createGetPathsRequest();
		Response rsp = PNFS.request(request);
		
		Map<String, String> args = rsp.getArgs();
		int num = 0;
		
		try {
			num = Integer.parseInt(args.get("paths"));
		} catch (NumberFormatException e) {
			throw new PNFSException("invalid response from ypfs server");
		}
		
		List<String> paths = new ArrayList<String>(num);
		
		for (int i = 1; i < num + 1; i++) {
			String path = args.get("path" + i);
			if (path != null) {
				paths.add(path);
			}
		}
		
		return paths;
	}
	
	protected Request createGetPathsRequest() {
		Request request = new Request(Command.GET_PATHS);
		request.addArg("class", getType());
		request.addArg("filename", getFilename());
		return request;
	}
	
	/*
	 * @see com.painiu.pnfs.File#enable()
	 */
	public void enable() throws PNFSException {
		throw new PNFSException("method not supported");
	}
	
	/*
	 * @see com.painiu.pnfs.File#disable()
	 */
	public void disable() throws PNFSException {
		throw new PNFSException("method not supported");
	}
	
	/*
	 * @see com.painiu.pnfs.File#delete()
	 */
	public void delete() throws PNFSException {
		PNFS.delete(this);
	}
	
	//~ Accessors ==============================================================

	/**
	 * @return the file
	 */
	public java.io.File getFile() {
		return file;
	}

	/**
	 * @param file the file to set
	 */
	public void setFile(java.io.File file) {
		this.file = file;
	}

	/**
	 * @return the username
	 */
	public String getUsername() {
		return username;
	}

	/**
	 * @param username the username to set
	 */
	public void setUsername(String username) {
		this.username = username;
	}

	/**
	 * @return the contentType
	 */
	public String getContentType() {
		return contentType;
	}
	
	/**
	 * @param contentType the contentType to set
	 */
	public void setContentType(String contentType) {
		this.contentType = contentType;
	}
	
	/**
	 * @return the filename
	 */
	public String getFilename() {
		return filename;
	}
	
	/**
	 * @param filename the filename to set
	 */
	public void setFilename(String filename) {
		this.filename = filename;
	}
}
