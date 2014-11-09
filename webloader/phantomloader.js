/*
 * Based on netsniff.js:
 * https://github.com/ariya/phantomjs/blob/master/examples/netsniff.js
 */
if (!Date.prototype.toISOString) {
    Date.prototype.toISOString = function () {
        function pad(n) { return n < 10 ? '0' + n : n; }
        function ms(n) { return n < 10 ? '00'+ n : n < 100 ? '0' + n : n }
        return this.getFullYear() + '-' +
            pad(this.getMonth() + 1) + '-' +
            pad(this.getDate()) + 'T' +
            pad(this.getHours()) + ':' +
            pad(this.getMinutes()) + ':' +
            pad(this.getSeconds()) + '.' +
            ms(this.getMilliseconds()) + 'Z';
    }
}

function createHAR(address, title, startTime, resources)
{
    var entries = [];

    resources.forEach(function (resource) {
        var request = resource.request,
            startReply = resource.startReply,
            endReply = resource.endReply;

        if (!request || !startReply || !endReply) {
            return;
        }

        // Exclude Data URI from HAR file because
        // they aren't included in specification
        if (request.url.match(/(^data:image\/.*)/i)) {
            return;
	}

        entries.push({
            startedDateTime: request.time.toISOString(),
            time: endReply.time - request.time,
            request: {
                method: request.method,
                url: request.url,
                httpVersion: "HTTP/1.1",
                cookies: [],
                headers: request.headers,
                queryString: [],
                headersSize: -1,
                bodySize: -1
            },
            response: {
                status: endReply.status,
                statusText: endReply.statusText,
                httpVersion: "HTTP/1.1",
                cookies: [],
                headers: endReply.headers,
                redirectURL: "",
                headersSize: -1,
                bodySize: startReply.bodySize,
                content: {
                    size: startReply.bodySize,
                    mimeType: endReply.contentType
                }
            },
            cache: {},
            timings: {
                blocked: 0,
                dns: -1,
                connect: -1,
                send: 0,
                wait: startReply.time - request.time,
                receive: endReply.time - startReply.time,
                ssl: -1
            },
            pageref: address
        });
    });

    return {
        log: {
            version: '1.2',
            creator: {
                name: "PhantomJS",
                version: phantom.version.major + '.' + phantom.version.minor +
                    '.' + phantom.version.patch
            },
            pages: [{
                startedDateTime: startTime.toISOString(),
                id: address,
                title: title,
                pageTimings: {
                    onLoad: page.endTime - page.startTime
                }
            }],
            entries: entries
        }
    };
}

var page = require('webpage').create(),
    system = require('system'),
	url
    error_msg = '';


if (system.args.length < 4) {
  console.log('Usage: phantomloader.js <some URL> <image path> <timeout (sec)> [<user agent>]');
  phantom.exit(1);
} else if (system.args.length === 5) {
  page.settings.userAgent = system.args[4];
}

url = system.args[1];
timeout = parseFloat(system.args[3]);

page.settings.resourceTimeout = 1000 * timeout;
page.onResourceTimeout = function(e) {
  console.log('FAILURE:timeout')
  phantom.exit(0);
};

page.onError = function (msg, trace) {
  console.log('FAILURE:' + msg + '\n');
  trace.forEach(function(item) {
    console.log('  ', item.file, ':', item.line);
  })
  phantom.exit(0);
}


page.address = url;
page.resources = [];

page.onLoadStarted = function () {
    page.startTime = new Date();
};

page.onResourceRequested = function (req) {
    page.resources[req.id] = {
        request: req,
        startReply: null,
        endReply: null
    };
};

page.onResourceReceived = function (res) {
    JSON.stringify(res);
    if (res.stage === 'start') {
        page.resources[res.id].startReply = res;
    }
    if (res.stage === 'end') {
        page.resources[res.id].endReply = res;
    }
};


page.onError = function(msg, trace) {

  console.log('error');

  var msgStack = ['ERROR: ' + msg];

  if (trace && trace.length) {
    msgStack.push('TRACE:');
    trace.forEach(function(t) {
      msgStack.push(' -> ' + t.file + ': ' + t.line + (t.function ? ' (in function "' + t.function +'")' : ''));
    });
  }

  console.error(msgStack.join('\n'));
  error_msg = msg;

};

page.onResourceError = function(resourceError) {
    error_msg = 'Error code: ' + resourceError.errorCode + '. Description: ' + resourceError.errorString + '  (' + resourceError.url + ' #' + resourceError.id + ')';
};


page.open(page.address, function (status) {
    var har;
    console.log(status)
    if (status !== 'success') {
    	console.log('FAILURE:' + error_msg);
        page.render(system.args[2])
        phantom.exit(1);
    } else {
        page.endTime = new Date();
    	t = Date.now() - t;
        page.title = page.evaluate(function () {
            return document.title;
        });
        har = createHAR(page.address, page.title, page.startTime, page.resources);
        page.render(system.args[2])
        console.log(JSON.stringify(har, undefined, 4));
		var t = page.endTime-page.startTime;
    	console.log('*=*=*=*\nSUCCESS:time=' + t + ';orig_url=' + url + ';final_url=' + page.url); // time in msec
        phantom.exit();
    }
});
