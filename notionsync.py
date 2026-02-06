"""
Notion Blog Sync Script
========================
Syncs blog posts from Notion to blogs.json for your static site
"""

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configuration - reads from .env file
NOTION_TOKEN = os.getenv('NOTION_SECRET')
DATABASE_ID = os.getenv('NOTIONDB_ID')
OUTPUT_FILE = 'blogs.json'

# Notion API settings
NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"

def get_headers():
    """Get headers for Notion API requests"""
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def query_database(database_id):
    """Query Notion database"""
    url = f"{BASE_URL}/databases/{database_id}/query"
    response = requests.post(url, headers=get_headers(), json={})
    response.raise_for_status()
    return response.json()

def get_blocks(page_id):
    """Get all blocks from a page"""
    url = f"{BASE_URL}/blocks/{page_id}/children"
    blocks = []
    has_more = True
    start_cursor = None
    
    while has_more:
        params = {'start_cursor': start_cursor} if start_cursor else {}
        response = requests.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        data = response.json()
        blocks.extend(data.get('results', []))
        has_more = data.get('has_more', False)
        start_cursor = data.get('next_cursor')
    
    return blocks

def rich_text_to_html(rich_text_array):
    """Convert Notion rich text to HTML"""
    if not rich_text_array:
        return ""
    html = ""
    for text_obj in rich_text_array:
        content = text_obj.get('plain_text', '')
        annotations = text_obj.get('annotations', {})
        if annotations.get('bold'):
            content = f"<strong>{content}</strong>"
        if annotations.get('italic'):
            content = f"<em>{content}</em>"
        if annotations.get('code'):
            content = f"<code>{content}</code>"
        if annotations.get('strikethrough'):
            content = f"<s>{content}</s>"
        if text_obj.get('href'):
            content = f'<a href="{text_obj["href"]}">{content}</a>'
        html += content
    return html

def block_to_html(block):
    """Convert Notion block to HTML"""
    block_type = block.get('type')
    block_content = block.get(block_type, {})
    
    if block_type == 'paragraph':
        text = rich_text_to_html(block_content.get('rich_text', []))
        return f"<p>{text}</p>" if text else ""
    elif block_type == 'heading_1':
        text = rich_text_to_html(block_content.get('rich_text', []))
        return f"<h1>{text}</h1>"
    elif block_type == 'heading_2':
        text = rich_text_to_html(block_content.get('rich_text', []))
        return f"<h2>{text}</h2>"
    elif block_type == 'heading_3':
        text = rich_text_to_html(block_content.get('rich_text', []))
        return f"<h3>{text}</h3>"
    elif block_type == 'code':
        code_text = rich_text_to_html(block_content.get('rich_text', []))
        language = block_content.get('language', 'plaintext')
        return f"<pre><code class='language-{language}'>{code_text}</code></pre>"
    elif block_type == 'bulleted_list_item':
        text = rich_text_to_html(block_content.get('rich_text', []))
        return f"<li>{text}</li>"
    elif block_type == 'numbered_list_item':
        text = rich_text_to_html(block_content.get('rich_text', []))
        return f"<li>{text}</li>"
    elif block_type == 'quote':
        text = rich_text_to_html(block_content.get('rich_text', []))
        return f"<blockquote>{text}</blockquote>"
    elif block_type == 'divider':
        return "<hr>"
    elif block_type == 'callout':
        text = rich_text_to_html(block_content.get('rich_text', []))
        icon = block_content.get('icon', {})
        emoji = icon.get('emoji', '💡') if icon.get('type') == 'emoji' else '💡'
        return f"<div class='callout'>{emoji} {text}</div>"
    elif block_type == 'toggle':
        text = rich_text_to_html(block_content.get('rich_text', []))
        return f"<details><summary>{text}</summary></details>"
    elif block_type == 'image':
        image_url = block_content.get('file', {}).get('url') or block_content.get('external', {}).get('url')
        caption = rich_text_to_html(block_content.get('caption', []))
        if image_url:
            if caption:
                return f'<figure><img src="{image_url}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'
            return f'<img src="{image_url}" alt="Image">'
    return ""

def blocks_to_html(blocks):
    """Convert blocks to HTML"""
    html_parts = []
    list_buffer = []
    current_list_type = None
    
    for block in blocks:
        block_type = block.get('type')
        
        if block_type in ['bulleted_list_item', 'numbered_list_item']:
            list_type = 'ul' if block_type == 'bulleted_list_item' else 'ol'
            if current_list_type != list_type:
                if list_buffer:
                    html_parts.append(f"<{current_list_type}>{''.join(list_buffer)}</{current_list_type}>")
                    list_buffer = []
                current_list_type = list_type
            list_buffer.append(block_to_html(block))
        else:
            if list_buffer:
                html_parts.append(f"<{current_list_type}>{''.join(list_buffer)}</{current_list_type}>")
                list_buffer = []
                current_list_type = None
            html = block_to_html(block)
            if html:
                html_parts.append(html)
        
        if block.get('has_children'):
            child_blocks = get_blocks(block['id'])
            child_html = blocks_to_html(child_blocks)
            if child_html:
                html_parts.append(child_html)
    
    if list_buffer:
        html_parts.append(f"<{current_list_type}>{''.join(list_buffer)}</{current_list_type}>")
    
    return ''.join(html_parts)

def extract_title(properties):
    """Extract title"""
    title_prop = properties.get('Title') or properties.get('Name')
    if title_prop and title_prop['type'] == 'title':
        rich_text = title_prop.get('title', [])
        return ''.join([text.get('plain_text', '') for text in rich_text])
    return "Untitled"

def extract_date(properties):
    """Extract date"""
    date_prop = properties.get('Date') or properties.get('Published')
    if date_prop:
        if date_prop['type'] == 'date' and date_prop.get('date'):
            date_str = date_prop['date']['start']
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_obj.strftime('%b %d, %Y')
        elif date_prop['type'] == 'created_time':
            date_obj = datetime.fromisoformat(date_prop['created_time'].replace('Z', '+00:00'))
            return date_obj.strftime('%b %d, %Y')
    return datetime.now().strftime('%b %d, %Y')

def extract_category(properties):
    """Extract category"""
    category_prop = properties.get('Category') or properties.get('Type')
    if category_prop:
        if category_prop['type'] == 'select' and category_prop.get('select'):
            return category_prop['select']['name']
        elif category_prop['type'] == 'multi_select' and category_prop.get('multi_select'):
            return category_prop['multi_select'][0]['name'] if category_prop['multi_select'] else "General"
    return "General"

def extract_tags(properties):
    """Extract tags"""
    tags_prop = properties.get('Tags') or properties.get('Labels')
    if tags_prop and tags_prop['type'] == 'multi_select':
        return [tag['name'] for tag in tags_prop.get('multi_select', [])]
    return []

def extract_excerpt(properties, content_html):
    """Extract or generate excerpt"""
    excerpt_prop = properties.get('Excerpt') or properties.get('Summary')
    if excerpt_prop and excerpt_prop['type'] == 'rich_text':
        rich_text = excerpt_prop.get('rich_text', [])
        excerpt = ''.join([text.get('plain_text', '') for text in rich_text])
        if excerpt:
            return excerpt
    
    if content_html:
        import re
        paragraphs = re.findall(r'<p>(.*?)</p>', content_html)
        if paragraphs:
            text = re.sub('<[^<]+?>', '', paragraphs[0])
            return text[:200] + '...' if len(text) > 200 else text
    return "No excerpt available."

def extract_published_status(properties):
    """Check if published"""
    status_prop = properties.get('Status') or properties.get('Published')
    if status_prop:
        if status_prop['type'] == 'checkbox':
            return status_prop.get('checkbox', False)
        elif status_prop['type'] == 'select' and status_prop.get('select'):
            return status_prop['select']['name'].lower() in ['published', 'live', 'public']
    return True

def sync_notion_to_blogs():
    """Main sync function"""
    print("=" * 60)
    print("  Notion to Blog JSON Sync")
    print("=" * 60)
    print()
    
    if not NOTION_TOKEN:
        print("❌ NOTION_SECRET not found in .env file!")
        return
    
    if not DATABASE_ID:
        print("❌ NOTIONDB_ID not found in .env file!")
        return
    
    print("🚀 Starting Notion blog sync...")
    print("✅ Credentials loaded from .env")
    
    try:
        print(f"📚 Fetching blog posts from database...")
        data = query_database(DATABASE_ID)
        pages = data.get('results', [])
        print(f"✅ Found {len(pages)} pages")
    except Exception as e:
        print(f"❌ Failed to query database: {e}")
        print("\n📝 Make sure you've:")
        print("   1. Shared your database with your integration")
        print("   2. Set the correct NOTIONDB_ID in .env")
        return
    
    blogs = []
    for idx, page in enumerate(pages, 1):
        try:
            properties = page.get('properties', {})
            
            if not extract_published_status(properties):
                print(f"⏭️  Skipping unpublished post {idx}")
                continue
            
            print(f"📄 Processing post {idx}/{len(pages)}...")
            
            title = extract_title(properties)
            date = extract_date(properties)
            category = extract_category(properties)
            tags = extract_tags(properties)
            
            print(f"   Fetching content for: {title}")
            blocks = get_blocks(page['id'])
            content_html = blocks_to_html(blocks)
            excerpt = extract_excerpt(properties, content_html)
            
            blog_entry = {
                "id": idx,
                "title": title,
                "excerpt": excerpt,
                "content": content_html,
                "date": date,
                "category": category,
                "tags": tags
            }
            
            blogs.append(blog_entry)
            print(f"   ✅ Processed: {title}")
            
        except Exception as e:
            print(f"   ❌ Error processing page {idx}: {e}")
            continue
    
    blogs.sort(key=lambda x: datetime.strptime(x['date'], '%b %d, %Y'), reverse=True)
    
    for idx, blog in enumerate(blogs, 1):
        blog['id'] = idx
    
    try:
        output_data = {"blogs": blogs}
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Successfully created {OUTPUT_FILE} with {len(blogs)} blog posts!")
        print(f"📁 File saved to: {os.path.abspath(OUTPUT_FILE)}")
    except Exception as e:
        print(f"\n❌ Failed to write output file: {e}")

if __name__ == "__main__":
    sync_notion_to_blogs()