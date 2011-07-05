/*
 * @(#)PhotoFile.java Nov 8, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs.files;

import java.io.File;

import com.painiu.pnfs.Request;
import com.painiu.pnfs.Response;
import com.painiu.pnfs.PNFS;
import com.painiu.pnfs.PNFSException;
import com.painiu.pnfs.PNFS.Path;

/**
 * <p>
 * <a href="PhotoFile.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public class PhotoFile extends AbstractFile {
	//~ Static fields/initializers =============================================

	private static final String TYPE_NAME = "photo";
	
	//~ Instance fields ========================================================

	private String secret;
	private int width;
	private int height;
	
	//~ Constructors ===========================================================

	public PhotoFile(String username, String filename) {
		super(username, filename);
	}
	
	public PhotoFile(String username, String filename, String secret) {
		super(username, filename);
		this.secret = secret;
	}
	
	public PhotoFile(String username, File file, String contentType, int width, int height) {
		super(username, file, contentType);
		this.width = width;
		this.height = height;
	}
	
	//~ Methods ================================================================
	
	/*
	 * @see com.painiu.pnfs.files.AbstractFile#createOpen()
	 */
	@Override
	protected Response createOpen() {
		Response response = super.createOpen();
		setSecret(response.getArgs().get("secret"));
		return response;
	}
	
	/*
	 * @see com.painiu.pnfs.files.AbstractFile#createCloseRequest(com.painiu.pnfs.YPFS.Path)
	 */
	@Override
	protected Request createCloseRequest(Path path) {
		Request request = super.createCloseRequest(path);
		request.addArg("secret", getSecret());
		request.addArg("width", String.valueOf(getWidth()));
		request.addArg("height", String.valueOf(getHeight()));
		
		return request;
	}
	
	/*
	 * @see com.painiu.pnfs.files.AbstractFile#createGetPathsRequest()
	 */
	@Override
	protected Request createGetPathsRequest() {
		Request request = super.createGetPathsRequest();
		request.getArgs().put("username", username);
		request.getArgs().put("secret", secret);
		return request;
	}
	
	/*
	 * @see com.painiu.pnfs.File#getType()
	 */
	public String getType() {
		return TYPE_NAME;
	}
	
	/*
	 * @see com.painiu.pnfs.files.AbstractFile#enable()
	 */
	@Override
	public void enable() throws PNFSException {
		PNFS.enable(this);
	}
	
	/*
	 * @see com.painiu.pnfs.files.AbstractFile#disable()
	 */
	@Override
	public void disable() throws PNFSException {
		PNFS.disable(this);
	}
	
	//~ Accessors ==============================================================

	/**
	 * @return the secret
	 */
	public String getSecret() {
		return secret;
	}
	
	/**
	 * @param secret the secret to set
	 */
	public void setSecret(String secret) {
		this.secret = secret;
	}

	/**
	 * @return the height
	 */
	public int getHeight() {
		return height;
	}

	/**
	 * @param height the height to set
	 */
	public void setHeight(int height) {
		this.height = height;
	}

	/**
	 * @return the width
	 */
	public int getWidth() {
		return width;
	}

	/**
	 * @param width the width to set
	 */
	public void setWidth(int width) {
		this.width = width;
	}
	
}