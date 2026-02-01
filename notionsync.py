import os
import json
from datetime import datetime
from notion_client import Client

# ============================================================================
# CONFIGURATION - Update these values
# ============================================================================

# Option 1: Set as environment variables (recommended)
NOTION_TOKEN = os.getenv('NOTION_TOKEN', 'YOUR_NOTION_INTEGRATION_TOKEN_HERE')
DATABASE_ID = os.getenv('NOTION_DATABASE_ID', 'YOUR_DATABASE_ID_HERE')

# Output file path
OUTPUT_FILE = 'blogs.json'

# ============================================================================
# Notion to HTML Conversion Functions
# ============================================================================

def notion_rich_text_to_html(rich_text_array):
    """Convert Notion rich text to HTML"""
    if not rich_text_array:
        return ""
    
    html = ""
    for text_obj in rich_text_array:
        content = text_obj.get('plain_text', '')
        annotations = text_obj.get('annotations', {})
        
        # Apply formatting
        if annotations.get('bold'):
            content = f"<strong>{content}</strong>"
        if annotations.get('italic'):
            content = f"<em>{content}</em>"
        if annotations.get('code'):
            content = f"<code>{content}</code>"
        if annotations.get('strikethrough'):
            content = f"<s>{content}</s>"
        
        # Handle links
        if text_obj.get('href'):
            content = f'<a href="{text_obj["href"]}">{content}</a>'
        
        html += content
    
    return html


def notion_block_to_html(block):
    """Convert a Notion block to HTML"""
    block_type = block.get('type')
    block_content = block.get(block_type, {})
    
    # Paragraph
    if block_type == 'paragraph':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        return f"<p>{text}</p>" if text else ""
    
    # Headings
    elif block_type == 'heading_1':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        return f"<h1>{text}</h1>"
    
    elif block_type == 'heading_2':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        return f"<h2>{text}</h2>"
    
    elif block_type == 'heading_3':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        return f"<h3>{text}</h3>"
    
    # Code block
    elif block_type == 'code':
        code_text = notion_rich_text_to_html(block_content.get('rich_text', []))
        language = block_content.get('language', 'plaintext')
        return f"<pre><code class='language-{language}'>{code_text}</code></pre>"
    
    # Bulleted list
    elif block_type == 'bulleted_list_item':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        return f"<li>{text}</li>"
    
    # Numbered list
    elif block_type == 'numbered_list_item':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        return f"<li>{text}</li>"
    
    # Quote
    elif block_type == 'quote':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        return f"<blockquote>{text}</blockquote>"
    
    # Divider
    elif block_type == 'divider':
        return "<hr>"
    
    # Callout
    elif block_type == 'callout':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        icon = block_content.get('icon', {})
        emoji = icon.get('emoji', '💡') if icon.get('type') == 'emoji' else '💡'
        return f"<div class='callout'>{emoji} {text}</div>"
    
    # Toggle
    elif block_type == 'toggle':
        text = notion_rich_text_to_html(block_content.get('rich_text', []))
        return f"<details><summary>{text}</summary></details>"
    
    # Image
    elif block_type == 'image':
        image_url = block_content.get('file', {}).get('url') or block_content.get('external', {}).get('url')
        caption = notion_rich_text_to_html(block_content.get('caption', []))
        if image_url:
            if caption:
                return f'<figure><img src="{image_url}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'
            return f'<img src="{image_url}" alt="Image">'
    
    return ""


def fetch_blocks(notion, page_id):
    """Fetch all blocks (content) from a Notion page"""
    blocks = []
    has_more = True
    start_cursor = None
    
    while has_more:
        response = notion.blocks.children.list(
            block_id=page_id,
            start_cursor=start_cursor
        )
        blocks.extend(response.get('results', []))
        has_more = response.get('has_more', False)
        start_cursor = response.get('next_cursor')
    
    return blocks


def blocks_to_html(notion, blocks):
    """Convert Notion blocks to HTML content"""
    html_parts = []
    list_buffer = []
    current_list_type = None
    
    for block in blocks:
        block_type = block.get('type')
        
        # Handle list items
        if block_type in ['bulleted_list_item', 'numbered_list_item']:
            list_type = 'ul' if block_type == 'bulleted_list_item' else 'ol'
            
            # If starting a new list or changing list type
            if current_list_type != list_type:
                # Close previous list if exists
                if list_buffer:
                    html_parts.append(f"<{current_list_type}>{''.join(list_buffer)}</{current_list_type}>")
                    list_buffer = []
                current_list_type = list_type
            
            list_buffer.append(notion_block_to_html(block))
        else:
            # Close any open list
            if list_buffer:
                html_parts.append(f"<{current_list_type}>{''.join(list_buffer)}</{current_list_type}>")
                list_buffer = []
                current_list_type = None
            
            # Add regular block
            html = notion_block_to_html(block)
            if html:
                html_parts.append(html)
        
        # Handle nested blocks (for toggles, etc.)
        if block.get('has_children'):
            child_blocks = fetch_blocks(notion, block['id'])
            child_html = blocks_to_html(notion, child_blocks)
            if child_html:
                html_parts.append(child_html)
    
    # Close any remaining list
    if list_buffer:
        html_parts.append(f"<{current_list_type}>{''.join(list_buffer)}</{current_list_type}>")
    
    return ''.join(html_parts)


# ============================================================================
# Property Extraction Functions
# ============================================================================

def extract_title(properties):
    """Extract title from Notion page properties"""
    title_prop = properties.get('Title') or properties.get('Name')
    if title_prop and title_prop['type'] == 'title':
        rich_text = title_prop.get('title', [])
        return ''.join([text.get('plain_text', '') for text in rich_text])
    return "Untitled"


def extract_date(properties):
    """Extract date from Notion page properties"""
    date_prop = properties.get('Date') or properties.get('Published')
    if date_prop:
        if date_prop['type'] == 'date' and date_prop.get('date'):
            date_str = date_prop['date']['start']
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_obj.strftime('%b %d, %Y')
        elif date_prop['type'] == 'created_time':
            date_obj = datetime.fromisoformat(date_prop['created_time'].replace('Z', '+00:00'))
            return date_obj.strftime('%b %d, %Y')
    
    # Fallback to created time
    return datetime.now().strftime('%b %d, %Y')


def extract_category(properties):
    """Extract category from Notion page properties"""
    category_prop = properties.get('Category') or properties.get('Type')
    if category_prop:
        if category_prop['type'] == 'select' and category_prop.get('select'):
            return category_prop['select']['name']
        elif category_prop['type'] == 'multi_select' and category_prop.get('multi_select'):
            return category_prop['multi_select'][0]['name'] if category_prop['multi_select'] else "General"
    return "General"


def extract_tags(properties):
    """Extract tags from Notion page properties"""
    tags_prop = properties.get('Tags') or properties.get('Labels')
    if tags_prop and tags_prop['type'] == 'multi_select':
        return [tag['name'] for tag in tags_prop.get('multi_select', [])]
    return []


def extract_excerpt(properties, content_html):
    """Extract or generate excerpt"""
    # Try to get from Notion properties first
    excerpt_prop = properties.get('Excerpt') or properties.get('Summary')
    if excerpt_prop and excerpt_prop['type'] == 'rich_text':
        rich_text = excerpt_prop.get('rich_text', [])
        excerpt = ''.join([text.get('plain_text', '') for text in rich_text])
        if excerpt:
            return excerpt
    
    # Generate from content (first paragraph)
    if content_html:
        # Extract text from first paragraph
        import re
        paragraphs = re.findall(r'<p>(.*?)</p>', content_html)
        if paragraphs:
            # Remove HTML tags and limit length
            text = re.sub('<[^<]+?>', '', paragraphs[0])
            return text[:200] + '...' if len(text) > 200 else text
    
    return "No excerpt available."


def extract_published_status(properties):
    """Check if the post is published"""
    status_prop = properties.get('Status') or properties.get('Published')
    if status_prop:
        if status_prop['type'] == 'checkbox':
            return status_prop.get('checkbox', False)
        elif status_prop['type'] == 'select' and status_prop.get('select'):
            return status_prop['select']['name'].lower() in ['published', 'live', 'public']
    return True  # Default to published if no status property


# ============================================================================
# Main Sync Function
# ============================================================================

def sync_notion_to_blogs():
    """Main function to sync Notion database to blogs.json"""
    print("🚀 Starting Notion blog sync...")
    
    # Initialize Notion client
    try:
        notion = Client(auth=NOTION_TOKEN)
        print("✅ Connected to Notion")
    except Exception as e:
        print(f"❌ Failed to connect to Notion: {e}")
        print("\n📝 Make sure you've set your NOTION_TOKEN correctly!")
        return
    
    # Query database
    try:
        print(f"📚 Fetching blog posts from database...")
        response = notion.databases.query(database_id=DATABASE_ID)
        pages = response.get('results', [])
        print(f"✅ Found {len(pages)} pages")
    except Exception as e:
        print(f"❌ Failed to query database: {e}")
        print("\n📝 Make sure you've:")
        print("   1. Shared your database with your integration")
        print("   2. Set the correct DATABASE_ID")
        return
    
    # Process each page
    blogs = []
    for idx, page in enumerate(pages, 1):
        try:
            properties = page.get('properties', {})
            
            # Check if published
            if not extract_published_status(properties):
                print(f"⏭️  Skipping unpublished post {idx}")
                continue
            
            print(f"📄 Processing post {idx}/{len(pages)}...")
            
            # Extract metadata
            title = extract_title(properties)
            date = extract_date(properties)
            category = extract_category(properties)
            tags = extract_tags(properties)
            
            # Fetch and convert content
            print(f"   Fetching content for: {title}")
            blocks = fetch_blocks(notion, page['id'])
            content_html = blocks_to_html(notion, blocks)
            
            # Generate excerpt
            excerpt = extract_excerpt(properties, content_html)
            
            # Create blog entry
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
    
    # Sort by date (newest first)
    blogs.sort(key=lambda x: datetime.strptime(x['date'], '%b %d, %Y'), reverse=True)
    
    # Re-assign IDs after sorting
    for idx, blog in enumerate(blogs, 1):
        blog['id'] = idx
    
    # Write to JSON file
    try:
        output_data = {"blogs": blogs}
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Successfully created {OUTPUT_FILE} with {len(blogs)} blog posts!")
        print(f"📁 File saved to: {os.path.abspath(OUTPUT_FILE)}")
    except Exception as e:
        print(f"\n❌ Failed to write output file: {e}")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Notion to Blog JSON Sync")
    print("=" * 60)
    print()
    
    # Validate configuration
    if NOTION_TOKEN == 'YOUR_NOTION_INTEGRATION_TOKEN_HERE':
        print("⚠️  Please set your NOTION_TOKEN!")
        print("   You can either:")
        print("   1. Set environment variable: export NOTION_TOKEN='your_token'")
        print("   2. Edit this script and replace YOUR_NOTION_INTEGRATION_TOKEN_HERE")
        print()
    
    if DATABASE_ID == 'YOUR_DATABASE_ID_HERE':
        print("⚠️  Please set your DATABASE_ID!")
        print("   You can either:")
        print("   1. Set environment variable: export NOTION_DATABASE_ID='your_db_id'")
        print("   2. Edit this script and replace YOUR_DATABASE_ID_HERE")
        print()
    
    if NOTION_TOKEN != 'YOUR_NOTION_INTEGRATION_TOKEN_HERE' and DATABASE_ID != 'YOUR_DATABASE_ID_HERE':
        sync_notion_to_blogs()
    else:
        print("❌ Cannot proceed without valid configuration.")
        print("\n📖 See setup instructions at the top of this script.")