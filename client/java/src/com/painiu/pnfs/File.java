/*
 * @(#)File.java Nov 8, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs;

import java.io.IOException;
import java.io.InputStream;

/**
 * <p>
 * <a href="File.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public interface File {
	
	public String getUsername();
	
	public void setUsername(String username);
	
	public String getFilename();
	
	public void setFilename(String filename);
	
	public String getContentType();
	
	public String getType();
	
	public InputStream getInputStream() throws PNFSException, IOException;
	
	public void store() throws PNFSException;
	
	public void enable() throws PNFSException;
	
	public void disable() throws PNFSException;
	
	public void delete() throws PNFSException;
}
