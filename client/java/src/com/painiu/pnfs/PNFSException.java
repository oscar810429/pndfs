/*
 * @(#)PNFSException.java Nov 9, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs;

/**
 * <p>
 * <a href="YPFSException.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public class PNFSException extends RuntimeException {
	private String code;
	private String message;
	
	public PNFSException() {
		super();
	}
	
	public PNFSException(String msg) {
		super(msg);
	}
	
	public PNFSException(String msg, Throwable cause) {
		super(msg, cause);
	}
	
	public PNFSException(String code, String message) {
		this.code = code;
		this.message = message;
	}
	
	/**
	 * @return the code
	 */
	public String getCode() {
		return code;
	}
	
	/*
	 * @see java.lang.Throwable#getMessage()
	 */
	@Override
	public String getMessage() {
		return message;
	}
}
