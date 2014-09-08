var fs = require('fs');
var path = require('path');
var http2 = require('/home/kyle/github/node_modules/http2');
var lengthStream = require('/home/kyle/github/node_modules/length-stream');

http2.globalAgent = new http2.Agent({
  log: require('/home/kyle/github/node_modules/http2/test/util').createLogger('client')
});

process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";

// Sending the request
var time = process.hrtime()
var return_code = 0
var size = 0
// It would be `var request = http2.get(process.argv.pop());` if we wouldn't care about plain mode
var options = require('url').parse(process.argv.pop());
options.plain = Boolean(process.env.HTTP2_PLAIN);
var request = http2.request(options);
request.end();

// Receiving the response
request.on('response', function(response) {  
  var lstream = lengthStream(lengthListener);
  response.pipe(lstream);
//  response.pipe(process.stdout);
  response.on('end', finish);
  return_code = response.statusCode;
});

function lengthListener(length) {
  size = length;
}

// Receiving push streams
request.on('push', function(pushRequest) {
  var filename = path.join(__dirname, '/push-' + push_count);
  push_count += 1;
  console.error('Receiving pushed resource: ' + pushRequest.url + ' -> ' + filename);
  pushRequest.on('response', function(pushResponse) {
    pushResponse.pipe(fs.createWriteStream(filename)).on('finish', finish);
  });
});

// Quitting after both the response and the associated pushed resources have arrived
var push_count = 0;
var finished = 0;
function finish() {
  finished += 1;
  if (finished === (1 + push_count)) {
    time = process.hrtime(time)
    console.log('http_code=' + return_code + ';final_url=NOT_SUPPORTED;time=' + (time[0] + time[1]/1000000000).toFixed(3) + ';size=' + size);
    process.exit();
  }
}
