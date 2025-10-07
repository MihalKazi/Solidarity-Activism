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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================================
# FIX 1: KEYRING ERROR - Critical for Render
# ==========================================
try:
    import keyring.backends.null
    keyring.set_keyring(keyring.backends.null.Keyring())
    print("✅ Keyring configured: null backend (server mode)")
except ImportError:
    print("⚠️  Keyring module not found - continuing without it")
except Exception as e:
    print(f"⚠️  Keyring configuration failed: {e}")

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

def get_enhanced_ydl_opts():
    """
    Get optimized yt-dlp options for SERVER deployment
    CRITICAL: No browser cookie extraction (causes keyring errors)
    """
    return {
        # Realistic browser simulation
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        
        # Complete browser headers
        'headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Cache-Control': 'max-age=0',
        },
        
        # Network settings - optimized for free tier servers
        'socket_timeout': 600,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        
        # Certificate handling
        'nocheckcertificate': True,
        
        # ==========================================
        # FIX 2: DISABLE COOKIE EXTRACTION - Critical!
        # ==========================================
        # This line was causing the keyring error
        # Servers don't have browsers installed
        'cookiesfrombrowser': None,  # MUST BE None for server deployment
        
        # Geo-bypass attempts
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        
        # Disable problematic features
        'youtube_include_dash_manifest': False,
        'youtube_include_hls_manifest': False,
        
        # Extractor arguments for better compatibility
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'configs'],
            }
        },
        
        # Network preferences
        'source_address': '0.0.0.0',  # Bind to all interfaces
        
        # Chunk size for downloads
        'http_chunk_size': 10485760,  # 10MB chunks
        
        # Logging
        'quiet': False,
        'no_warnings': False,
        'verbose': False,
        
        # Don't extract flat
        'extract_flat': False,
        
        # Add referer
        'referer': 'https://www.google.com/',
    }

def get_video_info(url):
    """Extract metadata without downloading - with enhanced error handling"""
    ydl_opts = get_enhanced_ydl_opts()
    ydl_opts.update({
        'quiet': True,
        'no_warnings': True,
        'verbose': False,
    })
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        
        # Provide user-friendly error messages
        if 'sign in' in error_msg.lower() or 'bot' in error_msg.lower():
            raise Exception('⚠️ Platform blocking detected. Try:\n1. A different video\n2. TikTok or Twitter/X (better success)\n3. Wait 5-10 minutes and retry')
        elif 'private' in error_msg.lower() or 'registered users' in error_msg.lower():
            raise Exception('🔒 Private video. Use a public video instead.')
        elif 'age' in error_msg.lower() or 'restricted' in error_msg.lower():
            raise Exception('🔞 Age-restricted content requires authentication.')
        elif 'not available' in error_msg.lower() or 'removed' in error_msg.lower():
            raise Exception('❌ Video unavailable (geo-blocked/removed/deleted).')
        elif 'copyright' in error_msg.lower():
            raise Exception('©️ Copyright restrictions prevent download.')
        elif 'live' in error_msg.lower():
            raise Exception('📡 Live streams cannot be downloaded.')
        elif 'unsupported url' in error_msg.lower():
            raise Exception('🔗 URL not supported. Check the platform list.')
        else:
            # Clean up error message
            clean_error = error_msg.replace('[0;31mERROR:[0m', '').strip()
            raise Exception(f'Unable to access: {clean_error[:200]}')
    except Exception as e:
        error_str = str(e)
        # Remove ANSI color codes
        clean_error = re.sub(r'\x1b\[[0-9;]*m', '', error_str)
        raise Exception(f'Error: {clean_error[:200]}')

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
        print(f"🏷️  Campaign: {solidarity}")
        
        info = get_video_info(url)
        
        # Extract comprehensive metadata
        metadata = {
            'title': info.get('title', 'Unknown Title'),
            'uploader': info.get('uploader') or info.get('channel') or info.get('creator') or 'Unknown',
            'url': url,
            'description': (info.get('description', '')[:500] + '...') if info.get('description') and len(info.get('description', '')) > 500 else info.get('description', ''),
            'duration': info.get('duration'),
            'viewCount': info.get('view_count', 0),
            'likeCount': info.get('like_count', 0),
            'thumbnail': info.get('thumbnail'),
            'platform': info.get('extractor_key', 'unknown').lower(),
            'extension': info.get('ext', 'mp4'),
            'size': info.get('filesize') or info.get('filesize_approx'),
            'mimeType': f"video/{info.get('ext', 'mp4')}",
            'solidarity': solidarity,
            'uploadDate': info.get('upload_date'),
            'availability': info.get('availability', 'public'),
            'width': info.get('width'),
            'height': info.get('height'),
            'fps': info.get('fps'),
            'format_note': info.get('format_note', 'best quality available')
        }
        
        print(f"✅ Metadata fetched successfully")
        print(f"📊 Platform: {metadata['platform']}")
        print(f"🎬 Title: {metadata['title'][:50]}...")
        
        return jsonify(metadata)
    
    except Exception as e:
        error_msg = str(e)
        # Remove ANSI color codes from error
        clean_error = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
        print(f"❌ Metadata error: {clean_error}")
        return jsonify({'error': clean_error}), 500

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
        
        print(f"\n{'='*60}")
        print(f"📥 DOWNLOAD REQUEST")
        print(f"{'='*60}")
        print(f"🔗 URL: {url}")
        print(f"🎯 Campaign: {solidarity}")
        print(f"📊 Quality: {quality}")
        
        # Create unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_solidarity = "".join(c for c in solidarity if c.isalnum() or c in (' ', '-', '_')).strip()
        
        # Sanitize filename
        safe_solidarity = re.sub(r'[<>:"/\\|?*]', '', safe_solidarity)
        if not safe_solidarity:
            safe_solidarity = "media"
        
        output_template = os.path.join(TEMP_DIR, f'{safe_solidarity}_{timestamp}_%(title).50s.%(ext)s')
        
        print(f"📁 Output template: {output_template}")
        
        # Get enhanced options and add download-specific settings
        ydl_opts = get_enhanced_ydl_opts()
        ydl_opts.update({
            # Format selection - prefer mp4 for maximum compatibility
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
            'outtmpl': output_template,
            
            # Force merge to mp4
            'merge_output_format': 'mp4',
            
            # Post-processing to ensure mp4 format
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
            'writeannotations': False,
            
            # Progress hooks for debugging
            'progress_hooks': [lambda d: print(f"⬇️  {d.get('status', 'downloading')}: {d.get('_percent_str', 'N/A')}")],
        })
        
        # Download the video
        print(f"\n{'='*60}")
        print(f"🚀 STARTING DOWNLOAD")
        print(f"{'='*60}\n")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("⬇️ Step 1: Extracting video information...")
            
            try:
                info = ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                # Remove ANSI codes
                clean_error = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
                print(f"❌ Extraction failed: {clean_error}")
                
                # User-friendly errors
                if 'sign in' in error_msg.lower() or 'bot' in error_msg.lower():
                    return jsonify({'error': '⚠️ Platform blocking detected. Try a different video or wait 5-10 minutes.'}), 400
                elif 'private' in error_msg.lower() or 'registered users' in error_msg.lower():
                    return jsonify({'error': '🔒 Private video. Use a public video instead.'}), 400
                elif 'age' in error_msg.lower() or 'restricted' in error_msg.lower():
                    return jsonify({'error': '🔞 Age-restricted content cannot be downloaded.'}), 400
                elif 'not available' in error_msg.lower():
                    return jsonify({'error': '❌ Video not available (geo-blocked/removed).'}), 400
                elif 'copyright' in error_msg.lower():
                    return jsonify({'error': '©️ Copyright restrictions prevent download.'}), 400
                else:
                    return jsonify({'error': f'Cannot access: {clean_error[:200]}'}), 400
            
            # Check for common issues
            formats = info.get('formats', [])
            if not formats:
                return jsonify({'error': 'No downloadable formats found'}), 400
            
            print(f"📊 Found {len(formats)} available formats")
            
            # Validate video availability
            if info.get('is_live'):
                return jsonify({'error': '📡 Live streams cannot be downloaded'}), 400
            
            if info.get('availability') in ['premium_only', 'subscriber_only']:
                return jsonify({'error': '💎 This content requires a subscription'}), 400
            
            if info.get('availability') == 'needs_auth':
                return jsonify({'error': '🔐 Authentication required. Try a public video.'}), 400
            
            # Now download
            print("⬇️ Step 2: Downloading video...")
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            print(f"📦 Download complete: {downloaded_file}")
        
        # Verify file exists
        if not os.path.exists(downloaded_file):
            print(f"❌ File not found at expected location: {downloaded_file}")
            # Try alternative extensions
            base = os.path.splitext(downloaded_file)[0]
            for ext in ['.mp4', '.webm', '.mkv', '.m4a', '.mp3', '.flv', '.avi']:
                alt_file = base + ext
                if os.path.exists(alt_file):
                    downloaded_file = alt_file
                    print(f"✅ Found file with alternative extension: {downloaded_file}")
                    break
        
        if not os.path.exists(downloaded_file):
            print(f"❌ CRITICAL: File does not exist after download")
            return jsonify({'error': 'Download failed - file not created. Platform may be blocking downloads.'}), 500
        
        # Verify file integrity
        file_size = os.path.getsize(downloaded_file)
        print(f"📏 File size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        if file_size < 1024:  # Less than 1KB
            print(f"❌ File too small: {file_size} bytes")
            os.remove(downloaded_file)
            return jsonify({'error': 'Download failed - file too small (likely error page).'}), 500
        
        # Check for HTML errors (common when downloads fail)
        with open(downloaded_file, 'rb') as f:
            first_bytes = f.read(min(1024, file_size))
            if b'<!DOCTYPE' in first_bytes or b'<html' in first_bytes:
                print("❌ File is HTML, not a video!")
                os.remove(downloaded_file)
                return jsonify({'error': 'Download failed - received error page. Video may be geo-blocked.'}), 500
        
        # Get MIME type
        mime_type = mimetypes.guess_type(downloaded_file)[0] or 'video/mp4'
        print(f"📄 MIME type: {mime_type}")
        
        # Create clean filename for download
        base_name = os.path.basename(downloaded_file)
        clean_name = f"{safe_solidarity}_{base_name}"
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', clean_name)
        
        # Ensure filename isn't too long (filesystem limits)
        if len(clean_name) > 200:
            name_part, ext = os.path.splitext(clean_name)
            clean_name = name_part[:190] + ext
        
        print(f"📤 Sending file to client: {clean_name}")
        print(f"✅ SUCCESS - Download ready\n{'='*60}\n")
        
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
                    print(f"🗑️  Cleaned up temporary file: {downloaded_file}")
            except Exception as e:
                print(f"⚠️  Cleanup warning: {str(e)}")
        
        return response
    
    except Exception as e:
        error_msg = str(e)
        # Remove ANSI color codes
        clean_error = re.sub(r'\x1b\[[0-9;]*m', '', error_msg)
        
        print(f"\n{'='*60}")
        print(f"❌ DOWNLOAD FAILED")
        print(f"{'='*60}")
        print(f"Error: {clean_error}")
        print(f"{'='*60}\n")
        
        # Cleanup on error
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
                print(f"🗑️  Cleaned up failed download file")
            except:
                pass
        
        return jsonify({'error': clean_error[:300]}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Solidarity Media Hub API',
        'version': '2.3.0',
        'yt_dlp_version': yt_dlp.version.__version__,
        'keyring_status': 'disabled (server mode)',
        'cookie_extraction': 'disabled (server mode)'
    })

@app.route('/api/platforms', methods=['GET'])
def get_platforms():
    """Get supported platforms and their status"""
    return jsonify({
        'platforms': {
            'excellent': ['TikTok', 'Twitter/X', 'Reddit', 'Vimeo', 'Dailymotion'],
            'good': ['YouTube (public)', 'Instagram (public)', 'SoundCloud'],
            'limited': ['Facebook (public only)', 'YouTube (age-restricted)', 'Instagram (private)'],
            'requires_auth': ['Facebook (most)', 'YouTube (some)', 'Private accounts']
        },
        'note': 'Success rate varies. Public content works best. Age-restricted and private content may fail.',
        'server_mode': 'Cookie extraction disabled - authentication-required content will fail'
    })

@app.route('/', methods=['GET'])
def home():
    """API home page"""
    return jsonify({
        'service': 'Solidarity Media Hub API',
        'version': '2.3.0',
        'yt_dlp_version': yt_dlp.version.__version__,
        'server_mode': 'Optimized for deployment (no browser cookies)',
        'endpoints': {
            '/api/metadata': 'POST - Get media metadata',
            '/api/download': 'POST - Download media',
            '/api/health': 'GET - Health check',
            '/api/platforms': 'GET - Supported platforms'
        },
        'best_platforms': [
            'TikTok - Excellent',
            'Twitter/X - Excellent',
            'Reddit - Very good',
            'Vimeo - Very good',
            'YouTube - Good (public videos)'
        ],
        'limitations': [
            'Age-restricted content not supported',
            'Private videos not supported',
            'Authentication-required content will fail'
        ],
        'note': 'Use public videos for best results.',
        'docs': 'See README.md for full documentation'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n{'='*60}")
    print(f"🚀 Solidarity Media Hub API")
    print(f"{'='*60}")
    print(f"Version: 2.3.0 (Server Optimized)")
    print(f"yt-dlp: {yt_dlp.version.__version__}")
    print(f"Port: {port}")
    print(f"Temp Dir: {TEMP_DIR}")
    print(f"Cookie Extraction: DISABLED (no browsers)")
    print(f"Keyring: NULL backend (server mode)")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=True)