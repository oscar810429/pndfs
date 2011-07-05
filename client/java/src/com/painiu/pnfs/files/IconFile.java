/*
 * @(#)IconFile.java Nov 8, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs.files;

import java.io.File;

/**
 * <p>
 * <a href="IconFile.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zhang Songfu
 * @version $Id$
 */
public class IconFile extends AbstractFile {
	//~ Static fields/initializers =============================================
	
	private static final String TYPE_NAME = "icon";
	
	//~ Instance fields ========================================================
	
	//~ Constructors ===========================================================

	/**
	 * @param username
	 * @param file
	 * @param contentType
	 */
	public IconFile(String username, File file) {
		super(username, file, null);
	}
	
	public IconFile(String username, String filename) {
		super(username, filename);
	}
	
	//~ Methods ================================================================

	/*
	 * @see com.painiu.pnfs.File#getType()
	 */
	public String getType() {
		return TYPE_NAME;
	}
	
	//~ Accessors ==============================================================

}
