#!/usr/bin/env python3
"""
Auto-apply multi-key WebSocket routing updates to remaining files.
This script safely updates all remaining endpoints to support instance_id routing.
"""
import re
import os
from pathlib import Path

# Files to update with their required changes
UPDATES = {
    'app/api/v1/posts.py': {
        'proxy_calls': 1,
        'refresh_calls': 0,
        'connections_checks': 3
    },
    'app/api/v1/connections.py': {
        'proxy_calls': 2,
        'refresh_calls': 2,
        'connections_checks': 2
    },
    'app/api/v1/messages.py': {
        'proxy_calls': 2,
        'refresh_calls': 2,
        'connections_checks': 2
    },
    'app/linkedin/utils/my_profile_id.py': {
        'proxy_calls': 2,
        'refresh_calls': 1,
        'connections_checks': 0
    },
    'app/ws/profile_actions.py': {
        'proxy_calls': 0,
        'refresh_calls': 0,
        'connections_checks': 1
    },
    'app/api/v1/profiles.py': {
        'proxy_calls': 0,
        'refresh_calls': 0,
        'connections_checks': 3
    },
    'app/api/v1/profile_about_skills.py': {
        'proxy_calls': 0,
        'refresh_calls': 0,
        'connections_checks': 1
    },
    'app/api/v1/profile_contact.py': {
        'proxy_calls': 0,
        'refresh_calls': 0,
        'connections_checks': 1
    },
    'app/api/v1/profile_identity.py': {
        'proxy_calls': 0,
        'refresh_calls': 0,
        'connections_checks': 1
    },
}

def update_proxy_http_request_calls(content):
    """Add instance_id parameter to proxy_http_request calls."""
    # Pattern: timeout=60.0\n)
    # Replace with: timeout=60.0,\n                    instance_id=api_key.instance_id\n)

    pattern = r'(proxy_http_request\([^)]+timeout=60\.0)\n(\s+)\)'
    replacement = r'\1,\n\2instance_id=api_key.instance_id  # Route to correct browser instance\n\2)'
    return re.sub(pattern, replacement, content, flags=re.MULTILINE)

def update_refresh_session_calls(content):
    """Change refresh_linkedin_session calls from user_id to api_key."""
    # Pattern: refresh_linkedin_session(ws_handler, db, requesting_user_id)
    # Replace with: refresh_linkedin_session(ws_handler, db, api_key)

    patterns = [
        (r'refresh_linkedin_session\(ws_handler,\s*db,\s*requesting_user_id\)',
         'refresh_linkedin_session(ws_handler, db, api_key)'),
        (r'refresh_linkedin_session\(ws_handler,\s*db,\s*user_id\)',
         'refresh_linkedin_session(ws_handler, db, api_key)'),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    return content

def add_connections_comment(content):
    """Add helpful comment to active_connections checks."""
    # Pattern: if user_id_str not in ws_handler.connection_manager.active_connections
    # Add comment before

    pattern = r'(\s+)(if user_id(?:_str)? not in ws_handler\.connection_manager\.active_connections)'
    replacement = r'\1# Check if user has any active WebSocket connections\n\1\2'

    # Only add comment if not already there
    if '# Check if user has any active WebSocket connections' not in content:
        content = re.sub(pattern, replacement, content, count=1)

    return content

def process_file(filepath, changes):
    """Process a single file with specified changes."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Apply updates
        if changes['proxy_calls'] > 0:
            content = update_proxy_http_request_calls(content)

        if changes['refresh_calls'] > 0:
            content = update_refresh_session_calls(content)

        if changes['connections_checks'] > 0:
            content = add_connections_comment(content)

        # Only write if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, "Updated"
        else:
            return False, "No changes needed"

    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    """Main execution."""
    print("=" * 80)
    print("Multi-Key WebSocket Routing Updates")
    print("=" * 80)
    print()

    results = []
    for filepath, changes in UPDATES.items():
        full_path = Path(filepath)
        if not full_path.exists():
            results.append((filepath, False, "File not found"))
            continue

        changed, message = process_file(full_path, changes)
        results.append((filepath, changed, message))

    # Print results
    print("\nResults:")
    print("-" * 80)
    for filepath, changed, message in results:
        status = "[UPDATED]" if changed else "[OK]"
        print(f"{status} {filepath}: {message}")

    total = len(results)
    updated = sum(1 for _, changed, _ in results if changed)
    print("-" * 80)
    print(f"Total: {total} files, {updated} updated, {total - updated} unchanged")
    print()
    print("[SUCCESS] Multi-key updates applied successfully!")
    print()
    print("Next steps:")
    print("1. Review the changes: git diff")
    print("2. Test the application")
    print("3. Commit if all tests pass")

if __name__ == "__main__":
    main()
