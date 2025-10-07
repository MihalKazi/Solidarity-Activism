import React, { useState } from 'react';
import { Download, Globe, AlertCircle, Loader2, Info, CheckCircle, Video, FileText, Music, Image } from 'lucide-react';

export default function SolidarityMediaHub() {
  const [mediaUrl, setMediaUrl] = useState('');
  const [metadata, setMetadata] = useState(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [solidarityName, setSolidarityName] = useState('');

  // Smart API URL detection - FIXED for local development
  const getApiBaseUrl = () => {
    // Force local development mode check FIRST
    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('192.168.');
    
    if (isLocal) {
      console.log('💻 Running locally, using local API');
      return 'http://localhost:5000';
    }
    
    // Check environment variable for production
    if (import.meta.env.VITE_API_URL) {
      console.log('🔧 Using environment variable:', import.meta.env.VITE_API_URL);
      return import.meta.env.VITE_API_URL;
    }
    
    // Default to production API
    console.log('🌐 Running in production, using production API');
    return 'https://solidarity-media-api.onrender.com';
  };

  const API_BASE_URL = `${getApiBaseUrl()}/api`;
  
  // Log the final API URL on component mount
  React.useEffect(() => {
    console.log('🔗 API Base URL:', API_BASE_URL);
  }, []);

  const supportedPlatforms = [
    { value: 'youtube', label: 'YouTube', icon: Video },
    { value: 'facebook', label: 'Facebook', icon: Video },
    { value: 'instagram', label: 'Instagram', icon: Image },
    { value: 'twitter', label: 'Twitter/X', icon: Music },
    { value: 'tiktok', label: 'TikTok', icon: Video },
    { value: 'vimeo', label: 'Vimeo', icon: Video },
    { value: 'reddit', label: 'Reddit', icon: Globe },
    { value: 'soundcloud', label: 'SoundCloud', icon: Music },
  ];

  const formatFileSize = (bytes) => {
    if (!bytes) return 'Unknown';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatNumber = (num) => {
    if (!num) return '0';
    return parseInt(num).toLocaleString();
  };

  const fetchMetadata = async () => {
    if (!mediaUrl.trim()) {
      setError('Please enter a valid media URL');
      return;
    }

    if (!solidarityName.trim()) {
      setError('Please enter the solidarity campaign name');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setMetadata(null);

    console.log('📡 Fetching metadata from:', `${API_BASE_URL}/metadata`);

    try {
      const response = await fetch(`${API_BASE_URL}/metadata`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          url: mediaUrl.trim(),
          solidarity: solidarityName.trim()
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch metadata');
      }

      console.log('✅ Metadata received:', data);
      setMetadata(data);
      setSuccess('Media information loaded successfully!');
    } catch (err) {
      console.error('❌ Metadata fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadMedia = async (quality = 'best') => {
    setDownloading(true);
    setError('');
    setProgress(0);

    console.log('📥 Starting download from:', `${API_BASE_URL}/download`);

    try {
      const response = await fetch(`${API_BASE_URL}/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          url: mediaUrl.trim(),
          solidarity: solidarityName.trim(),
          quality: quality
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Download failed');
      }

      const contentLength = response.headers.get('content-length');
      const total = parseInt(contentLength, 10);
      let loaded = 0;

      const reader = response.body.getReader();
      const chunks = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        chunks.push(value);
        loaded += value.length;

        if (total) {
          setProgress(Math.round((loaded / total) * 100));
        }
      }

      const blob = new Blob(chunks);
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `${solidarityName}_${metadata?.title || 'media'}.${metadata?.extension || 'mp4'}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(a);

      console.log('✅ Download complete');
      setSuccess('Media archived successfully for the movement!');
      setProgress(100);
    } catch (err) {
      console.error('❌ Download error:', err);
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  const downloadMetadataJSON = () => {
    if (!metadata) return;

    const data = {
      solidarity_campaign: solidarityName,
      platform: metadata.platform || 'unknown',
      title: metadata.title,
      uploader: metadata.uploader,
      url: metadata.url,
      description: metadata.description,
      duration: metadata.duration,
      viewCount: metadata.viewCount,
      likeCount: metadata.likeCount,
      thumbnail: metadata.thumbnail,
      archived_at: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${solidarityName}_${metadata.platform}_metadata.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const downloadMetadataCSV = () => {
    if (!metadata) return;

    const csv = [
      'Field,Value',
      `Solidarity Campaign,"${solidarityName}"`,
      `Platform,${metadata.platform || 'unknown'}`,
      `Title,"${(metadata.title || '').replace(/"/g, '""')}"`,
      `Uploader,${metadata.uploader || 'Unknown'}`,
      `URL,${metadata.url}`,
      `Views,${metadata.viewCount || 0}`,
      `Likes,${metadata.likeCount || 0}`,
      `Duration,${metadata.duration || 0}`,
      `Archived At,${new Date().toISOString()}`,
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${solidarityName}_${metadata.platform}_metadata.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-600 via-indigo-600 to-blue-600 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-t-2xl p-8">
          <div className="flex items-center gap-4 mb-4">
            <div className="p-3 bg-gradient-to-br from-purple-600 to-indigo-600 rounded-2xl">
              <Globe className="w-10 h-10 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Solidarity Activism Hub
              </h1>
              <p className="text-gray-600 text-lg">
                Universal Media Archival Tool
              </p>
            </div>
          </div>
          
          <div className="flex flex-wrap gap-2 mt-4">
            {supportedPlatforms.map((p) => {
              const Icon = p.icon;
              return (
                <span key={p.value} className="bg-gradient-to-r from-purple-100 to-indigo-100 text-purple-700 px-3 py-1.5 rounded-full text-xs font-semibold flex items-center gap-1.5">
                  <Icon size={14} />
                  {p.label}
                </span>
              );
            })}
          </div>
        </div>

        <div className="bg-white rounded-b-2xl shadow-2xl p-8">
          <div className="space-y-5 mb-6">
            <div>
              <label className="block text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                <Globe className="w-4 h-4" />
                Solidarity Campaign Name *
              </label>
              <input
                type="text"
                value={solidarityName}
                onChange={(e) => setSolidarityName(e.target.value)}
                placeholder="e.g., Palestine, Ukraine, Climate Justice, Human Rights"
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:border-purple-500 focus:ring-4 focus:ring-purple-200 outline-none transition"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                <Video className="w-4 h-4" />
                Media URL *
              </label>
              <input
                type="url"
                value={mediaUrl}
                onChange={(e) => setMediaUrl(e.target.value)}
                placeholder="Paste video/image/audio link from any supported platform"
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:border-purple-500 focus:ring-4 focus:ring-purple-200 outline-none transition"
                onKeyPress={(e) => e.key === 'Enter' && fetchMetadata()}
              />
            </div>

            <button
              onClick={fetchMetadata}
              disabled={loading}
              className="w-full py-4 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl font-bold text-lg hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-3 shadow-lg"
            >
              {loading ? (
                <>
                  <Loader2 className="w-6 h-6 animate-spin" />
                  Analyzing Media...
                </>
              ) : (
                <>
                  <Download className="w-6 h-6" />
                  Fetch & Archive for Movement
                </>
              )}
            </button>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-50 border-l-4 border-red-500 rounded-r-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-red-700">{error}</p>
            </div>
          )}

          {success && (
            <div className="mb-6 p-4 bg-green-50 border-l-4 border-green-500 rounded-r-lg flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
              <p className="text-green-700">{success}</p>
            </div>
          )}

          {metadata && (
            <div className="space-y-6">
              <div className="border-2 border-purple-200 rounded-xl overflow-hidden">
                {metadata.thumbnail && (
                  <img
                    src={metadata.thumbnail}
                    alt={metadata.title}
                    className="w-full h-64 object-cover"
                  />
                )}
                
                <div className="p-6 space-y-4 bg-gradient-to-br from-purple-50 to-indigo-50">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">
                      {metadata.title || metadata.filename}
                    </h2>
                    <p className="text-purple-700 font-bold text-lg mb-1 flex items-center gap-2">
                      <Globe className="w-5 h-5" />
                      {solidarityName}
                    </p>
                    <p className="text-gray-700">
                      By: {metadata.uploader || 'Unknown'}
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    {metadata.viewCount && (
                      <div className="bg-white p-4 rounded-lg shadow-sm">
                        <p className="text-xs text-gray-600 font-semibold">Views</p>
                        <p className="text-xl font-bold text-blue-700">
                          {formatNumber(metadata.viewCount)}
                        </p>
                      </div>
                    )}
                    {metadata.likeCount && (
                      <div className="bg-white p-4 rounded-lg shadow-sm">
                        <p className="text-xs text-gray-600 font-semibold">Likes</p>
                        <p className="text-xl font-bold text-green-700">
                          {formatNumber(metadata.likeCount)}
                        </p>
                      </div>
                    )}
                    {metadata.duration && (
                      <div className="bg-white p-4 rounded-lg shadow-sm">
                        <p className="text-xs text-gray-600 font-semibold">Duration</p>
                        <p className="text-xl font-bold text-purple-700">
                          {formatDuration(metadata.duration)}
                        </p>
                      </div>
                    )}
                  </div>

                  {metadata.size && (
                    <div className="bg-white p-4 rounded-lg shadow-sm">
                      <p className="text-xs text-gray-600 font-semibold mb-1">File Info</p>
                      <p className="text-sm text-gray-700">
                        <span className="font-semibold">Size:</span> {formatFileSize(metadata.size)} • 
                        <span className="font-semibold ml-2">Type:</span> {metadata.mimeType || metadata.extension}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {downloading && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold text-gray-700">
                      Archiving for the movement...
                    </span>
                    <span className="text-sm font-bold text-purple-600">
                      {progress}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-purple-500 to-indigo-500 h-full rounded-full transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <button
                  onClick={() => downloadMedia('best')}
                  disabled={downloading}
                  className="py-3 px-4 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-xl font-bold hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg"
                >
                  <Video className="w-5 h-5" />
                  Download Media
                </button>
                
                <button
                  onClick={downloadMetadataJSON}
                  className="py-3 px-4 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl font-bold hover:from-green-600 hover:to-emerald-600 transition-all flex items-center justify-center gap-2 shadow-lg"
                >
                  <FileText className="w-5 h-5" />
                  Export JSON
                </button>

                <button
                  onClick={downloadMetadataCSV}
                  className="py-3 px-4 bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-xl font-bold hover:from-blue-600 hover:to-cyan-600 transition-all flex items-center justify-center gap-2 shadow-lg"
                >
                  <Download className="w-5 h-5" />
                  Export CSV
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl p-6 mt-6 border-2 border-purple-200 shadow-lg">
          <h4 className="font-bold text-gray-900 mb-3 flex items-center gap-2">
            <Info className="w-5 h-5 text-purple-600" />
            Mission Statement
          </h4>
          <ul className="text-sm text-gray-700 space-y-2">
            <li>Archive important solidarity content for historical documentation</li>
            <li>Preserve activist media that may be removed or censored</li>
            <li>Secure and ethical archival for human rights movements</li>
            <li>Respect copyright and fair use for educational/archival purposes</li>
            <li>Support grassroots movements worldwide</li>
          </ul>
        </div>

        <div className="bg-gradient-to-r from-purple-100 to-indigo-100 rounded-2xl p-4 mt-4 text-center border-2 border-purple-300">
          <p className="text-sm text-gray-700">
            <span className="font-bold text-purple-800">Developed by Mehal</span>
            <span className="mx-2">•</span>
            <span className="font-semibold text-indigo-700">Inspired by Muri</span>
          </p>
        </div>
      </div>
    </div>
  );
}