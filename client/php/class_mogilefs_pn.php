<?
class MogileFSClass{
    var $socket;
    var $error;
    
    /**
     * Constructor
     * 
     * TODO
     */
    function MogileFSClass( $domain = null,
               $hosts = null,
               $root = '' )
    {
        global $wgMogileTrackers, $wgDBname;

        if ($domain == null)
            $domain=$wgDBname;

        if ($hosts == null) {
            if ($wgMogileTrackers!=null) {
                $hosts=$wgMogileTrackers;
            } else {
                die("wgMogileTrackers empty, please define hosts");
            }
        }

        $this->domain = $domain;
        $this->hosts  = $hosts;
        $this->root   = $root;
        $this->error  = '';
    }

    /**
     * Factory method
     * Creates a new MogileFS object and tries to connect to a
     * mogilefsd.
     *
     * Returns false if it can't connect to any mogilefsd.
     *
     * TODO
     */
    function NewMogileFS( $domain = null,
                  $hosts = null,
                  $root = '' )
    {
        global $wgDBname; 

        if ($domain == null)
            $domain=$wgDBname;

        $mfs = new MogileFSClass( $domain, $hosts, $root );
        return ( $mfs->connect() ? $mfs : false );
    }

    /**
     * Connect to a mogilefsd
     * Scans through the list of daemons and tries to connect one.
     */
    function connect()
    {
        foreach ( $this->hosts as $host ) {
            list($ip,$port)=split(':',$host,2);
            if ($port==null)
                $port=6001;    
            $this->socket = fsockopen( $ip, $port );
            if ( $this->socket ) {
                break;
            }
        }

        return $this->socket;
    }

    /**
     * Send a request to mogilefsd and parse the result.
     * @private
     */
    function doRequest( $cmd,$args=array() )
    {
        $params=' class='.urlencode($this->domain);

        foreach ($args as $key => $value)
            $params.='&'.urlencode($key)."=".urlencode(iconv('gbk','utf-8',$value));

        if ( ! $this->socket ) {
            $this->connect();
        }
        fwrite( $this->socket, $cmd . $params."\r\n" );
        $line = fgets( $this->socket );
        $words = explode( ' ', $line );
        if ( $words[0] == 'OK' ) {
            parse_str( trim( $words[1] ), $result );
        } else {
            $result = false;
            $this->error = join(" ",$words);
        }
        return $result;
    }

    /**
     * Get an array of paths
     */
    function getPaths( $username = null, $filename = null )
    {
        $res = $this->doRequest( "GET_PATHS", array("username"=>$username,'filename'=>$filename));
        return $res;
    }

    /** 
     * Delete a file from system
     */
    function delete ( $username = null, $filename = null )
    {
        $res = $this->doRequest( "DELETE", array("username"=>$username,'filename'=>$filename));
        if ($res===false)
            return false;
        return true;
    }
    
    
    /** 
     * enable a file from system
     */
     
    function enable ( $username = null, $filename = null )
    {
        $res = $this->doRequest( "ENABlE", array("username"=>$username,'filename'=>$filename));
        if ($res===false)
            return false;
        return true;
    }
    
    /** 
     * disable a file from system
     */
     
    function disable ( $username = null, $filename = null )
    {
        $res = $this->doRequest( "DISABLE", array("username"=>$username,'filename'=>$filename));
        if ($res===false)
            return false;
        return true;
    }
    
    /**
     * Save a file to the MogileFS
     * TODO
     */
    function saveFile( $username = null, $filename = null)
    {
        $res = $this->doRequest( "CREATE_OPEN", array("username"=>$username,'filename'=>''));
        print_r($res);

        if ( ! $res )
            return false;
            
        if ( preg_match( '/^http:\/\/([a-z0-9.-]*):([0-9]*)\/(.*)$/', $res['path_'.$res['dev_count']], $matches ) ) {
            $host = $matches[1];
            $port = $matches[2];
            $path = $matches[3];

            // $fout = fopen( $res['path'], 'w' );

            $fin = fopen( $filename, 'r' );
            $ch = curl_init();
            curl_setopt($ch,CURLOPT_PUT,1);
            curl_setopt($ch,CURLOPT_URL, $res['path_'.$res['dev_count']]);
            curl_setopt($ch,CURLOPT_VERBOSE, 0);
            curl_setopt($ch,CURLOPT_INFILE, $fin);
            curl_setopt($ch,CURLOPT_INFILESIZE, filesize($filename));
            curl_setopt($ch,CURLOPT_TIMEOUT, 4);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            if(!curl_exec($ch)) {
                $this->error=curl_error($ch);
                curl_close($ch);
                return false;
            }
            curl_close($ch);

            $closeres = $this->doRequest( "CREATE_CLOSE", array(
                "class" => $this->domain,
                "devid" => $res['devid_'.$res['dev_count']],
                "fid"   => $res['fid'],
                "size"   => filesize($filename),
                "path"  => urldecode($res['path_'.$res['dev_count']]),
                "filename"=> $res['filename'],
                "username"=> $res['username'],
                "secret" => $res['secret'],
                "width" => "720",
                "height" => "480",
                "content_type"=> "image/jpeg"
                ));
  
  
            if ($closeres===false) {
                return false;
            } else {
                return true;
            }
        }
    }
}


?>