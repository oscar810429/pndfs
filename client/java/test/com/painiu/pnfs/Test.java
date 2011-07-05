/*
 * @(#)Test.java Jul 20, 2008
 * 
 * Copyright 2008 Painiu. All rights reserved.
 */
package com.painiu.pnfs;

import java.util.List;
import java.util.Properties;

import com.painiu.pnfs.PNFS;
import com.painiu.pnfs.files.IconFile;
import com.painiu.pnfs.files.PhotoFile;

/**
 * <p>
 * <a href="Test.java.html"><i>View Source</i></a>
 * </p>
 *
 * @author Zola Zhou
 * @version $Id$
 */
public class Test {
	public static void main(String[] args) throws Exception {
		Properties props = new Properties();
		props.put("servers", "192.168.152.129:7001");
		PNFS.initialize(props);
		
		PhotoFile f = new PhotoFile("oscar810429", new java.io.File("c:\\S5000171.JPG"),"image/jpeg", 720, 480);
        
		
		f.store();
		//f.enable();
		
		//IconFile iconFile = new IconFile("zhangsf810429", new java.io.File("c:\\746395a998f3.jpg"));
		//iconFile.store();
		
        //		for (int i = 0; i < 5; i++) {
		/*
		PhotoFile f = new PhotoFile("zola", new java.io.File("/Users/zola/tmp/testdata/test1.jpg"), 
				"image/jpeg", 720, 480);

		f.store();

		System.out.println(f.getFilename());
		System.out.println(f.getSecret());
		*/
		
//		PhotoFile f = new PhotoFile("zola", "646884ade32d");
//		f.disable();
		
//		Thread.sleep(1000);
		
//		f.enable();
//		}
//		PhotoFile f = new PhotoFile("zola", "1643049ccbda");
//		f.delete();
		//List<UserFlow> flows = PNFS.getUserFlows("zola");
		//for (UserFlow flow : flows) {
		//	System.out.println(flow.getMonth() + " : " + flow.getFlow());
		//}
	}
}
