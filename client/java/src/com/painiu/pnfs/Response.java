/*
 * @(#)Response.java Nov 12, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs;

import java.io.UnsupportedEncodingException;
import java.net.URLDecoder;
import java.util.HashMap;
import java.util.Map;

/**
 * <p>
 * <a href="Response.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public class Response {
	//~ Static fields/initializers =============================================

	public enum State {
		OK,
		ERR
	}
	
	//~ Instance fields ========================================================

	private State state;
	
	private Map<String, String> args;
	
	private String code;
	private String message;
	
	//~ Constructors ===========================================================
	
	public static Response okResponse(Map<String, String> args) {
		return new Response(State.OK, args, null, null);
	}
	
	public static Response errResponse(String code, String message) {
		return new Response(State.ERR, null, code, message);
	}
	
	public Response(State state, Map<String, String> args, String code, String message) {
		this.state = state;
		this.args = args;
		this.code = code;
		this.message = message;
	}
	
	//~ Methods ================================================================

	public static Response decode(String response) {
		if (response == null) {
			throw new PNFSException("Null response");
		}
		
		Response rsp = null;
		response = response.trim();
		int space = response.indexOf(' ');
		if (space == -1 && response.length() == 2 
				&& response.charAt(0) == 'O' && response.charAt(1) == 'K') {
			rsp = Response.okResponse(new HashMap<String, String>(0));
		} else if (space == 2 && response.charAt(0) == 'O' && response.charAt(1) == 'K') {
			Map<String, String> args = new HashMap<String, String>();
			
			// decode key/value pairs
			String key = null;
			String value = null;
			int last = space + 1;
			
			for (int i = last; i < response.length(); i++) {
				switch (response.charAt(i)) {
				case '&':
					value = response.substring(last, i);
					try {
						value = URLDecoder.decode(value, PNFS.TEXT_ENCODING);
					} catch (UnsupportedEncodingException e) {}
					last = i + 1;
					if (key != null) {
						args.put(key, value);
						key = null;
						value = null;
					}
					break;
				case '=':
					key = response.substring(last, i);
					last = i + 1;
					break;
				default:
					break;
				}
			}
			
			if (key != null) { // last key/value pair
				value = response.substring(last);
				try {
					value = URLDecoder.decode(value, PNFS.TEXT_ENCODING);
				} catch (UnsupportedEncodingException e) {}
				args.put(key, value);
			}
			
			rsp = Response.okResponse(args);
		} else if (space == 3) {
			int secondSpace = response.indexOf(' ', space + 1);
			if (secondSpace != -1) {
				String code = response.substring(space + 1, secondSpace);
				String message = response.substring(secondSpace + 1);
				try {
					message = URLDecoder.decode(message, PNFS.TEXT_ENCODING);
				} catch (UnsupportedEncodingException e) {}
				rsp = Response.errResponse(code, message);
			}
		}
		
		if (rsp == null) {
			rsp = Response.errResponse(null, response);
		}
		
		return rsp;
	}
	
	//~ Accessors ==============================================================
	
	/**
	 * @return the args
	 */
	public Map<String, String> getArgs() {
		if (args == null) {
			args = new HashMap<String, String>();
		}
		return args;
	}

	/**
	 * @param args the args to set
	 */
	public void setArgs(Map<String, String> args) {
		this.args = args;
	}

	/**
	 * @return the code
	 */
	public String getCode() {
		return code;
	}

	/**
	 * @param code the code to set
	 */
	public void setCode(String code) {
		this.code = code;
	}

	/**
	 * @return the message
	 */
	public String getMessage() {
		return message;
	}

	/**
	 * @param message the message to set
	 */
	public void setMessage(String message) {
		this.message = message;
	}

	/**
	 * @return the state
	 */
	public State getState() {
		return state;
	}

	/**
	 * @param state the state to set
	 */
	public void setState(State state) {
		this.state = state;
	}

}
