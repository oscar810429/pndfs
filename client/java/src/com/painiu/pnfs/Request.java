/*
 * @(#)Request.java Nov 12, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs;

import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/**
 * <p>
 * <a href="Request.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public class Request {
	//~ Static fields/initializers =============================================

	public enum Command {
		GET_PATHS("get_paths"),
		
		CREATE_OPEN("create_open"),
		
		CREATE_CLOSE("create_close"),
		
		DISABLE("disable"),
		
		ENABLE("enable"),
		
		DELETE("delete"),
		
		SET_LEVEL("set_level"),
		
		SET_MAX_FLOW("set_max_flow"),

		SET_VIP("set_vip"),
		
		CUSTOM_SIZE("custom_size"),
		
		GET_FLOWS("get_flows");
		
		private final String name;
		
		Command(String name) {
			this.name = name;
		}
		
		public String getName() {
			return this.name;
		}
	}
	
	//~ Instance fields ========================================================

	private Command command;
	
	private Map<String, String> args;
	
	//~ Constructors ===========================================================

	public Request(Command command) {
		this(command, null);
	}
	
	public Request(Command command, Map<String, String> args) {
		this.command = command;
		this.args = args;
	}
	
	//~ Methods ================================================================

	public String encode() {
		StringBuffer sb = new StringBuffer();
		sb.append(getCommand().getName());
		
		if (getArgs() != null) {
			sb.append(' ');
			
			Iterator<Map.Entry<String, String>> it = getArgs().entrySet().iterator();
			while (it.hasNext()) {
				Map.Entry<String, String> entry = it.next();
				sb.append(entry.getKey()).append('=');
				if (entry.getValue() != null) {
					try {
						sb.append(URLEncoder.encode(entry.getValue().toString(), PNFS.TEXT_ENCODING));
					} catch (UnsupportedEncodingException e) {
						sb.append(entry.getValue().toString());
					}
				}
				if (it.hasNext()) {
					sb.append('&');
				}
			}
		}
		sb.append("\r\n");
        System.out.println(sb.toString());
		return sb.toString();
	}
	
	public void addArg(String name, Object value) {
		if (args == null) {
			args = new HashMap<String, String>();
		}
		args.put(name, value == null ? "" : value.toString());
	}
	
	//~ Accessors ==============================================================
	
	/**
	 * @return the args
	 */
	public Map<String, String> getArgs() {
		return args;
	}

	/**
	 * @param args the args to set
	 */
	public void setArgs(Map<String, String> args) {
		this.args = args;
	}

	/**
	 * @return the command
	 */
	public Command getCommand() {
		return command;
	}

	/**
	 * @param command the command to set
	 */
	public void setCommand(Command command) {
		this.command = command;
	}
	
}

