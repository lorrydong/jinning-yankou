const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = 8080;
const ROOT = __dirname;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.mp3': 'audio/mpeg',
  '.json': 'application/json',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
};

const server = http.createServer((req, res) => {
  let pathname = decodeURIComponent(url.parse(req.url).pathname);
  
  // Handle load-annotation GET — return the most recent annotation file
  if (pathname === '/load-annotation' && req.method === 'GET') {
    const files = fs.readdirSync(ROOT).filter(f => f.startsWith('标注导出_') && f.endsWith('.json'));
    if (files.length === 0) {
      res.writeHead(404, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ ok: false, error: '服务器上没有找到标注记录' }));
      return;
    }
    // Sort by name (which includes timestamp) to get the newest
    files.sort().reverse();
    const target = files[0];
    try {
      const content = fs.readFileSync(path.join(ROOT, target), 'utf-8');
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(content);
    } catch(e) {
      res.writeHead(500, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
      res.end(JSON.stringify({ ok: false, error: '读取文件失败: ' + e.message }));
    }
    return;
  }

  // Handle list-annotations GET — list all annotation files on server
  if (pathname === '/list-annotations' && req.method === 'GET') {
    const files = fs.readdirSync(ROOT).filter(f => f.startsWith('标注导出_') && f.endsWith('.json'));
    files.sort().reverse();
    res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
    res.end(JSON.stringify({ ok: true, files }));
    return;
  }

  // Handle save-annotation POST
  if (pathname === '/save-annotation' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = '标注导出_' + timestamp + '.json';
        const filePath = path.join(ROOT, filename);
        fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ ok: true, file: filename }));
      } catch(e) {
        res.writeHead(400, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }
  
  if (pathname === '/') pathname = '/index.html';
  
  const filePath = path.join(ROOT, pathname);
  
  // Security: ensure we're within ROOT
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }
  
  fs.stat(filePath, (err, stat) => {
    if (err) {
      res.writeHead(404);
      res.end('Not Found');
      return;
    }
    
    const ext = path.extname(filePath).toLowerCase();
    const mime = MIME[ext] || 'application/octet-stream';
    const fileSize = stat.size;
    
    // Handle byte-range requests (for audio seeking)
    const range = req.headers.range;
    
    if (range) {
      const parts = range.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
      const chunkSize = end - start + 1;
      
      res.writeHead(206, {
        'Content-Range': `bytes ${start}-${end}/${fileSize}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunkSize,
        'Content-Type': mime,
        'Cache-Control': 'public, max-age=2592000, immutable',
        'Access-Control-Allow-Origin': '*',
      });
      
      const stream = fs.createReadStream(filePath, { start, end });
      stream.pipe(res);
      stream.on('error', () => res.end());
    } else {
      // Aggressive caching for offline: images/audio = 30 days, HTML/JS = 1 day
      let cacheMaxAge = 86400; // 1 day default
      if (ext === '.mp3') cacheMaxAge = 2592000;  // 30 days for audio
      else if (ext === '.jpg' || ext === '.jpeg' || ext === '.png' || ext === '.webp') cacheMaxAge = 2592000; // 30 days for images
      else if (ext === '.html') cacheMaxAge = 86400; // 1 day for HTML
      else if (ext === '.js') cacheMaxAge = 86400; // 1 day for JS
      else if (ext === '.json') cacheMaxAge = 86400; // 1 day for JSON
      
      res.writeHead(200, {
        'Content-Type': mime,
        'Content-Length': fileSize,
        'Accept-Ranges': 'bytes',
        'Cache-Control': `public, max-age=${cacheMaxAge}, immutable`,
        'Access-Control-Allow-Origin': '*',
      });
      
      const stream = fs.createReadStream(filePath);
      stream.pipe(res);
      stream.on('error', () => res.end());
    }
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`📿 晋宁焰口点读服务已启动`);
  console.log(`🌐 本地访问: http://localhost:${PORT}`);
  console.log(`🌐 互联网访问: http://140.83.62.197:${PORT}`);
  console.log(`📄 ${ROOT}`);
});
