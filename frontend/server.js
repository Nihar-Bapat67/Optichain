import http from "http";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 3000;
const DIST_DIR = path.join(__dirname, "dist");

const MIME_TYPES = {
  ".html": "text/html",
  ".js": "application/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".eot": "application/vnd.ms-fontobject",
  ".webp": "image/webp",
};

const server = http.createServer((req, res) => {
  // Strip query string for file resolution
  const urlPath = req.url.split("?")[0];
  let filePath = path.join(DIST_DIR, urlPath);

  // Resolve the file, falling back to index.html for SPA routing
  const serveFile = (targetPath) => {
    fs.readFile(targetPath, (err, data) => {
      if (err) {
        // Any read error on a non-root path falls back to index.html
        if (targetPath !== path.join(DIST_DIR, "index.html")) {
          serveFile(path.join(DIST_DIR, "index.html"));
        } else {
          res.writeHead(500);
          res.end("Internal Server Error");
        }
        return;
      }

      const ext = path.extname(targetPath).toLowerCase();
      const contentType = MIME_TYPES[ext] || "application/octet-stream";

      res.writeHead(200, { "Content-Type": contentType });
      res.end(data);
    });
  };

  // If the path has no extension, treat it as a SPA route → index.html
  const ext = path.extname(urlPath);
  if (!ext) {
    serveFile(path.join(DIST_DIR, "index.html"));
  } else {
    serveFile(filePath);
  }
});

server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
