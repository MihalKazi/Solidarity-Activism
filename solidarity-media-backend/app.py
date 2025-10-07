from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import json
from datetime import datetime
import tempfile
import shutil
import mimetypes
import re

app = Flask(__name__)

# BULLETPROOF CORS Configuration
CORS(app, 
     resources={r"/api/*": {"origins": "*"}},
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "OPTIONS"],
     supports_credentials=False)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

# Configure temp directory
TEMP_DIR = tempfile.gettempdir()

def get_video_info(url):
    """Extract metadata without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'cookiesfrombrowser': None,  # Don't use browser cookies
        'no_check_certificates': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

@app.route('/api/metadata', methods=['POST', 'OPTIONS'])
def get_metadata():
    if request.method == 'OPTIONS':
        return '', 204
    
    try:
        data = request.json
        url = data.get('url')
        solidarity = data.get('solidarity', 'Unknown')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        print(f"📡 Fetching metadata for: {url}")
        info = get_video_info(url)
        
        metadata = {
            'title': info.get('title'),
            'uploader': info.get('uploader') or info.get('channel'),
            'url': url,
            'description': info.get('description'),
            'duration': info.get('duration'),
            'viewCount': info.get('view_count'),
            'likeCount': info.get('like_count'),
            'thumbnail': info.get('thumbnail'),
            'platform': info.get('extractor_key', '').lower(),
            'extension': info.get('ext', 'mp4'),
            'size': info.get('filesize') or info.get('filesize_approx'),
            'mimeType': f"video/{info.get('ext', 'mp4')}",
            'solidarity': solidarity
        }
        
        print(f"✅ Metadata fetched successfully")
        return jsonify(metadata)
    
    except Exception as e:
        print(f"❌ Metadata error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST', 'OPTIONS'])
def download_media():
    if request.method == 'OPTIONS':
        return '', 204
    
    downloaded_file = None
    
    try:
        data = request.json
        url = data.get('url')
        solidarity = data.get('solidarity', 'media')
        quality = data.get('quality', 'best')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        print(f"📥 Starting download for: {url}")
        print(f"🎯 Solidarity: {solidarity}")
        print(f"📊 Quality: {quality}")
        
        # Create unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_solidarity = "".join(c for c in solidarity if c.isalnum() or c in (' ', '-', '_')).strip()
        
        # Sanitize filename more aggressively
        safe_solidarity = re.sub(r'[<>:"/\\|?*]', '', safe_solidarity)
        if not safe_solidarity:
            safe_solidarity = "media"
        
        output_template = os.path.join(TEMP_DIR, f'{safe_solidarity}_{timestamp}_%(title).50s.%(ext)s')
        
        print(f"📁 Output template: {output_template}")
        
        # FIXED: Better yt-dlp options to avoid HTML downloads
        ydl_opts = {
            # Format selection - prefer mp4, avoid DASH formats
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            
            # Logging
            'quiet': False,
            'no_warnings': False,
            'verbose': True,
            
            # Network settings
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            
            # User agent and headers
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            
            # Avoid certificate issues
            'no_check_certificates': True,
            
            # Don't use browser cookies (can cause issues)
            'cookiesfrombrowser': None,
            
            # Force merge to mp4
            'merge_output_format': 'mp4',
            
            # Post-processing
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            
            # Don't download extra files
            'writeinfojson': False,
            'writethumbnail': False,
            'writedescription': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            
            # Important: Force IPv4 (can prevent some issues)
            'prefer_ipv4': True,
            
            # Extract info before download
            'extract_flat': False,
            'force_generic_extractor': False,
        }
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("⬇️ Extracting video info...")
            info = ydl.extract_info(url, download=False)
            
            # Check if we actually have video formats
            formats = info.get('formats', [])
            if not formats:
                return jsonify({'error': 'No downloadable formats found for this video'}), 400
            
            print(f"📊 Found {len(formats)} formats")
            
            # Check for common issues
            if info.get('is_live'):
                return jsonify({'error': 'Live streams cannot be downloaded'}), 400
            
            if info.get('availability') == 'premium_only':
                return jsonify({'error': 'This content requires a premium subscription'}), 400
            
            if info.get('availability') == 'needs_auth':
                return jsonify({'error': 'This content requires authentication'}), 400
            
            # Now download
            print("⬇️ Starting download...")
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            print(f"📦 Downloaded file: {downloaded_file}")
        
        # Verify file exists and is not HTML
        if not os.path.exists(downloaded_file):
            print(f"❌ File not found: {downloaded_file}")
            # Try to find the file with different extensions
            base = os.path.splitext(downloaded_file)[0]
            for ext in ['.mp4', '.webm', '.mkv', '.m4a', '.mp3', '.flv']:
                alt_file = base + ext
                if os.path.exists(alt_file):
                    downloaded_file = alt_file
                    print(f"✅ Found file with alternative extension: {downloaded_file}")
                    break
        
        if not os.path.exists(downloaded_file):
            return jsonify({'error': 'Download failed - file not created'}), 500
        
        # CRITICAL: Check if file is actually HTML (common error)
        file_size = os.path.getsize(downloaded_file)
        print(f"📏 File size: {file_size} bytes")
        
        if file_size < 1024:  # Less than 1KB is suspicious
            return jsonify({'error': 'Download failed - file too small (possible HTML error page)'}), 500
        
        # Read first few bytes to detect HTML
        with open(downloaded_file, 'rb') as f:
            first_bytes = f.read(1024)
            if b'<!DOCTYPE' in first_bytes or b'<html' in first_bytes:
                print("❌ File is HTML, not a video!")
                os.remove(downloaded_file)
                return jsonify({'error': 'Download failed - received HTML instead of video. The video may be geo-blocked, age-restricted, or require login.'}), 500
        
        # Detect MIME type
        mime_type = mimetypes.guess_type(downloaded_file)[0]
        if not mime_type:
            mime_type = 'video/mp4'
        
        print(f"📄 MIME type: {mime_type}")
        
        # Get clean filename for download
        base_name = os.path.basename(downloaded_file)
        clean_name = f"{safe_solidarity}_{base_name}"
        
        # Remove any remaining problematic characters
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', clean_name)
        
        print(f"📤 Sending file: {clean_name}")
        
        # Send file
        response = send_file(
            downloaded_file,
            mimetype=mime_type,
            as_attachment=True,
            download_name=clean_name
        )
        
        # Cleanup after sending
        @response.call_on_close
        def cleanup():
            try:
                if downloaded_file and os.path.exists(downloaded_file):
                    os.remove(downloaded_file)
                    print(f"🗑️ Cleaned up: {downloaded_file}")
            except Exception as e:
                print(f"⚠️ Cleanup error: {str(e)}")
        
        print("✅ Download complete!")
        return response
    
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        print(f"❌ yt-dlp Download error: {error_msg}")
        
        # Cleanup on error
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
            except:
                pass
        
        # Provide helpful error messages
        if 'private video' in error_msg.lower():
            return jsonify({'error': 'This video is private'}), 400
        elif 'age' in error_msg.lower():
            return jsonify({'error': 'This video is age-restricted and cannot be downloaded'}), 400
        elif 'not available' in error_msg.lower():
            return jsonify({'error': 'This video is not available in your region'}), 400
        elif 'copyright' in error_msg.lower():
            return jsonify({'error': 'This video has been removed due to copyright'}), 400
        else:
            return jsonify({'error': f'Download failed: {error_msg}'}), 500
    
    except Exception as e:
        print(f"❌ Download error: {str(e)}")
        # Cleanup on error
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
            except:
                pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'Solidarity Media Hub API'})

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Solidarity Media Hub API',
        'version': '2.0.0',
        'endpoints': {
            '/api/metadata': 'POST - Get media metadata',
            '/api/download': 'POST - Download media',
            '/api/health': 'GET - Health check'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting Solidarity Media Hub API on port {port}")
    print(f"📁 Temp directory: {TEMP_DIR}")
    app.run(host='0.0.0.0', port=port, debug=True)