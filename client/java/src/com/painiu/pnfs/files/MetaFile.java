/*
 * @(#)MetaFile.java Nov 14, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs.files;

import java.io.File;

import com.painiu.pnfs.Request;
import com.painiu.pnfs.PNFSException;

/**
 * <p>
 * <a href="MetaFile.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public class MetaFile extends AbstractFile {
	//~ Static fields/initializers =============================================
	
	private static final String TYPE_NAME = "meta";
	
	//~ Instance fields ========================================================
	
	//~ Constructors ===========================================================

	/**
	 * @param username
	 * @param file
	 * @param contentType
	 */
	public MetaFile(String username, String filename, File file) {
		super(username, file, null);
		this.filename = filename;
	}
	
	public MetaFile(String username, String filename) {
		super(username, filename);
	}
	
	//~ Methods ================================================================

	/*
	 * @see com.painiu.pnfs.File#getType()
	 */
	public String getType() {
		return TYPE_NAME;
	}
	
	/*
	 * @see com.painiu.pnfs.files.AbstractFile#delete()
	 */
	@Override
	public void delete() throws PNFSException {
		throw new PNFSException("method not supported");
	}
	
	/*
	 * @see com.painiu.pnfs.files.AbstractFile#createGetPathsRequest()
	 */
	@Override
	protected Request createGetPathsRequest() {
		Request request = super.createGetPathsRequest();
		request.getArgs().put("username", username);
		return request;
	}
	
	//~ Accessors ==============================================================

}
