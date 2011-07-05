from urllib import quote_plus, unquote_plus

def encode_url_string(args):
	if args is None:
		return ""
	return "&".join(
		["%s=%s" % (
					quote_plus(str(k)),
					quote_plus(str(v))
				   ) 
		for k, v in args.items() if v]
	)

def decode_url_string(arg):
	out = {}
	if not arg:
		return out

	#arg = unquote_plus(arg)
	pairs = arg.split('&')
	for pair in pairs:
		name, value = pair.split('=', 1)
		out[name] = unquote_plus(value)

	return out
