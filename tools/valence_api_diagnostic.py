#!/usr/bin/env python3
"""Optional, manual read-only diagnostic for a configured Valence server.

This tool is not part of CI. It makes network requests only when explicitly
run by a developer with VALENCE_URL and, when needed, VALENCE_API configured.
"""

import sys
import json
import os
import requests
from urllib.parse import urljoin

# Load .env file if present
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

load_env()

class ReadOnlyValenceDiagnostics:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url.rstrip('/')
        self.api_url = urljoin(self.base_url, '/api/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ValenceCon-TestHarness/1.0',
            'Accept': 'application/json',
        })
        if api_key:
            # Valence uses X-Api-Key header, not Bearer token
            self.session.headers['X-Api-Key'] = api_key
        
        self.results = []
    
    def test(self, name, method, path, **kwargs):
        """Run a test and record result"""
        url = urljoin(self.api_url, path.lstrip('/'))
        try:
            if method == 'GET':
                resp = self.session.get(url, timeout=10, **kwargs)
            elif method == 'HEAD':
                resp = self.session.head(url, timeout=10, **kwargs)
            else:
                return self._record(name, method, path, False, f"Method {method} not allowed in safety harness")
            
            success = resp.status_code < 400
            self._record(name, method, path, success, 
                        f"HTTP {resp.status_code}", 
                        resp.headers.get('Content-Type'),
                        len(resp.content) if resp.content else 0)
            return success, resp
        except Exception as e:
            self._record(name, method, path, False, str(e))
            return False, None
    
    def _record(self, name, method, path, success, message, content_type=None, size=0):
        self.results.append({
            'name': name,
            'method': method,
            'path': path,
            'success': success,
            'message': message,
            'content_type': content_type,
            'response_size': size
        })
        status = "✅" if success else "❌"
        print(f"  {status} {name}: {method} {path} - {message}")
    
    def run_safety_tests(self):
        """Run all safe read-only tests"""
        print(f"\n{'='*60}")
        print(f"Valence API Read-Only Diagnostics")
        print(f"Base URL: {self.base_url}")
        print(f"API URL:  {self.api_url}")
        print(f"{'='*60}\n")
        
        # Test 1: Server Info (always safe)
        print("📋 Server Information Tests")
        self.test("About", "GET", "/about")
        self.test("Health Check", "GET", "/health")
        
        # Test 2: Libraries (read-only)
        print("\n📚 Library Tests")
        self.test("List Libraries", "GET", "/libraries")
        
        # Test 3: Profiles (read-only listing)
        print("\n👤 Profile Tests")
        self.test("List Profiles", "GET", "/profiles")
        
        # Test 4: Library Facets (genres, years, etc.)
        print("\n🏷️  Library Facets Tests")
        self.test("Library Facets", "GET", "/library-facets")
        
        # Test 5: Continue Watching / Up Next
        print("\n▶️  Continue Watching Tests")
        self.test("Up Next", "GET", "/up-next")
        self.test("Progress", "GET", "/progress")
        
        # Test 6: Search (read-only)
        print("\n🔍 Search Tests")
        self.test("Catalogue Search", "GET", "/admin/catalogue/search", params={'q': 'test', 'limit': 1})
        
        # Test 7: Live TV (if available)
        print("\n📺 Live TV Tests")
        self.test("Live Sources", "GET", "/live/sources")
        self.test("Live Channels", "GET", "/live/channels")
        self.test("Live Guide", "GET", "/live/guide")
        
        # Test 8: Music (if available)
        print("\n🎵 Music Tests")
        self.test("Music Albums", "GET", "/music/albums", params={'limit': 1})
        self.test("Music Artists", "GET", "/music/artists", params={'limit': 1})
        self.test("Music Genres", "GET", "/music/genres")
        
        # Test 9: Books (if available)
        print("\n📖 Books Tests")
        self.test("Books", "GET", "/books", params={'limit': 1})
        
        # Test 10: Collections
        print("\n📦 Collections Tests")
        self.test("Collections", "GET", "/collections", params={'limit': 1})
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        passed = sum(1 for r in self.results if r['success'])
        failed = sum(1 for r in self.results if not r['success'])
        print(f"Total: {len(self.results)} | Passed: {passed} | Failed: {failed}")
        
        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r['success']:
                    print(f"  ❌ {r['name']}: {r['message']}")
        
        return failed == 0
    
    def test_specific_library(self, library_id):
        """Test a specific library's items (read-only)"""
        print(f"\n📂 Testing Library: {library_id}")
        self.test(f"Library Items (first 5)", "GET", f"/libraries/{library_id}/items", params={'limit': 5})
        self.test(f"Library Shows", "GET", f"/libraries/{library_id}/shows")
    
    def test_media_item(self, media_id):
        """Test a specific media item (read-only)"""
        print(f"\n🎬 Testing Media Item: {media_id}")
        self.test("Media Details", "GET", f"/media/{media_id}")
        # Note: /media/{id}/artwork endpoint not available on this Valence version
        # Artwork URLs come from posterUrl/backdropUrl in item data directly
        self.test("Media Poster URL (from item data)", "GET", f"/media/{media_id}", params={'fields': 'posterUrl'})
    
    def export_results(self, filepath):
        """Export test results to JSON"""
        with open(filepath, 'w') as f:
            json.dump({
                'base_url': self.base_url,
                'api_url': self.api_url,
                'summary': {
                    'total': len(self.results),
                    'passed': sum(1 for r in self.results if r['success']),
                    'failed': sum(1 for r in self.results if not r['success'])
                },
                'results': self.results
            }, f, indent=2)
        print(f"\n📄 Results exported to: {filepath}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Optional read-only Valence API diagnostics')
    parser.add_argument('url', nargs='?', default=os.environ.get('VALENCE_URL'), help='Valence server URL (e.g., http://localhost:8420) or set VALENCE_URL in .env')
    parser.add_argument('--api-key', default=os.environ.get('VALENCE_API'), help='API key for authentication (optional) or set VALENCE_API in .env')
    parser.add_argument('--library', help='Test specific library ID')
    parser.add_argument('--media', help='Test specific media ID')
    parser.add_argument('--output', help='Export results to JSON file')
    args = parser.parse_args()
    
    if not args.url:
        print("❌ Error: VALENCE_URL not set. Provide as argument or set in .env")
        sys.exit(1)
    
    print("This diagnostic performs only read-only GET and HEAD requests.")
    print("   No POST/PUT/DELETE requests will be made.")
    print("   Safe for production testing.\n")
    
    harness = ReadOnlyValenceDiagnostics(args.url, args.api_key)
    success = harness.run_safety_tests()
    
    if args.library:
        harness.test_specific_library(args.library)
    
    if args.media:
        harness.test_media_item(args.media)
    
    if args.output:
        harness.export_results(args.output)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
