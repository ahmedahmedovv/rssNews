import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import sys
import time
import feedparser
from datetime import datetime, timedelta
import pytz
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch

class RSSFinder:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # Create base output directory with today's date
        self.today = datetime.now().strftime('%Y%m%d')
        self.base_output_dir = f'rss_outputs_{self.today}'
        if not os.path.exists(self.base_output_dir):
            os.makedirs(self.base_output_dir)
        
        # Initialize merged results file
        self.merged_file = os.path.join(self.base_output_dir, f'all_news_{self.today}.txt')
        with open(self.merged_file, 'w', encoding='utf-8') as f:
            f.write(f"All RSS News - {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write("=" * 80 + "\n\n")
    
    def get_site_folder_name(self, url):
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        folder_path = os.path.join(self.base_output_dir, domain)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        return folder_path

    def append_to_merged_file(self, url, entries):
        with open(self.merged_file, 'a', encoding='utf-8') as f:
            f.write(f"\n\nNews from {url}\n")
            f.write("-" * 80 + "\n")
            if entries:
                for entry in entries:
                    f.write(f"\nTitle: {entry['title']}\n")
                    f.write(f"Published: {entry['published']}\n")
                    f.write(f"Link: {entry['link']}\n")
                    f.write(f"Description: {entry['description'][:500]}...\n")
                    f.write("-" * 40 + "\n")
            else:
                f.write("No entries found.\n")

    def save_recent_entries_to_file(self, url, feeds):
        folder_path = self.get_site_folder_name(url)
        timestamp = datetime.now().strftime('%H%M%S')
        filename = os.path.join(folder_path, f"news_{self.today}_{timestamp}.txt")
        
        all_entries = []
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Recent news from {url}\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            for feed_url in feeds:
                f.write(f"\nFeed: {feed_url}\n")
                f.write("-" * 80 + "\n")
                
                entries = self.get_recent_entries(feed_url)
                all_entries.extend(entries)  # Collect all entries for merged file
                
                if entries:
                    for entry in entries:
                        f.write(f"\nTitle: {entry['title']}\n")
                        f.write(f"Published: {entry['published']}\n")
                        f.write(f"Link: {entry['link']}\n")
                        f.write(f"Description: {entry['description'][:500]}...\n")
                        f.write("-" * 40 + "\n")
                else:
                    f.write("No entries found in this feed.\n")
        
        # Save found RSS feeds to a separate file
        feeds_file = os.path.join(folder_path, f"rss_feeds_{self.today}.txt")
        with open(feeds_file, 'w', encoding='utf-8') as f:
            f.write(f"RSS feeds for {url}\n")
            f.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            for feed in feeds:
                f.write(f"{feed}\n")
        
        # Append to merged file
        self.append_to_merged_file(url, all_entries)
        
        return filename

    def clean_url(self, url):
        """Clean URL by removing quotes and extra spaces"""
        url = url.strip().strip('"').strip("'")
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url

    def process_urls_from_file(self, filename='websites.txt'):
        # Get the absolute path to the data directory
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filename = os.path.join(current_dir, 'data', filename)
        
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                # Clean URLs while reading and remove any trailing commas
                urls = [self.clean_url(line.strip()) for line in file if line.strip() and not line.startswith('#')]
            
            print(f"\nFound {len(urls)} websites to process")
            processed_sites = {}
            failed_sites = []
            
            for index, url in enumerate(urls, 1):
                try:
                    print(f"\n{'='*80}")
                    print(f"Processing website ({index}/{len(urls)}): {url}")
                    
                    if self.is_feed_url(url):
                        print(f"✓ URL is a direct RSS feed")
                        feeds = [url]
                    else:
                        feeds = self.find_rss_feeds(url)
                    
                    if feeds:
                        print(f"✓ Found {len(feeds)} RSS feeds")
                        output_file = self.save_recent_entries_to_file(url, feeds)
                        print(f"✓ Saved results to: {output_file}")
                        processed_sites[url] = feeds
                    else:
                        print(f"✗ No RSS feeds found for {url}")
                        failed_sites.append((url, "No RSS feeds found"))
                except Exception as e:
                    print(f"✗ Error processing {url}: {str(e)}")
                    failed_sites.append((url, str(e)))
                    continue
            
            # Generate detailed report
            report_file = self.generate_report(urls, processed_sites, failed_sites)
            
            # Print summary
            print("\n" + "="*80)
            print(f"Processing complete!")
            print(f"Successfully processed: {len(processed_sites)}/{len(urls)} websites")
            print(f"Detailed report saved to: {report_file}")
            
            if failed_sites:
                failed_file = os.path.join(self.base_output_dir, f'failed_sites_{self.today}.txt')
                with open(failed_file, 'w', encoding='utf-8') as f:
                    f.write(f"Failed websites - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*80 + "\n\n")
                    for url, error in failed_sites:
                        f.write(f"URL: {url}\nError: {error}\n\n")
                print(f"Failed sites have been saved to: {failed_file}")
            
            print(f"All successful results have been merged into: {self.merged_file}")
        
            # After processing all sites, create PDF report
            print("\nCreating PDF report...")
            pdf_file = self.create_pdf_report()
            if pdf_file:
                print(f"PDF report saved to: {pdf_file}")
            
            print("\nProcessing complete!")
        
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found")
            with open(filename, 'w', encoding='utf-8') as file:
                file.write("www.wnp.pl\ndefence24.pl\n")
            print(f"Created example {filename} file. Please add your websites and run again.")
        except Exception as e:
            print(f"Error processing file: {str(e)}")

    def is_feed_url(self, url):
        """Check if the URL itself is a feed"""
        try:
            feed = feedparser.parse(url)
            return len(feed.entries) > 0
        except:
            return False

    def find_rss_feeds(self, url):
        # Clean the URL first
        url = url.strip().strip('"').strip("'")
        
        # If the URL itself is a feed, return it directly
        if any(url.lower().endswith(ext) for ext in ['.xml', '.rss', '_rss', '/_rss', '/feed', '/feed/', '.feed']):
            if self.is_feed_url(url):
                return [url]
    
        try:
            print(f"Searching for RSS feeds on {url}...")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            feeds = set()
            
            # Look for RSS/Atom feed links
            feed_links = soup.find_all('link', type=re.compile(r'application/(rss|atom)\+xml'))
            for link in feed_links:
                href = link.get('href', '')
                if href:
                    feeds.add(urljoin(url, href))
            
            # If no feeds found but URL looks like a feed, try the URL itself
            if not feeds and self.is_feed_url(url):
                return [url]
                
            return list(feeds)
            
        except requests.exceptions.RequestException as e:
            # If the URL itself is a feed, return it even if website scraping fails
            if self.is_feed_url(url):
                return [url]
            print(f"Network error: {str(e)}")
            return []
        except Exception as e:
            print(f"Error: {str(e)}")
            return []

    def is_valid_feed(self, content):
        """Check if content appears to be a valid RSS/Atom feed"""
        try:
            # Look for common RSS/Atom elements
            return bool(re.search(r'<(rss|feed|channel)[^>]*>', content))
        except:
            return False

    def get_recent_entries(self, feed_url, days=1):
        try:
            print(f"\nProcessing feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            recent_entries = []
            
            # Get current time in UTC
            now = datetime.now(pytz.UTC)
            cutoff_date = now - timedelta(days=days)
            
            print(f"Found {len(feed.entries)} total entries")
            
            for entry in feed.entries:
                try:
                    # Print raw entry data for debugging
                    print("\nEntry raw data:")
                    for key, value in entry.items():
                        print(f"{key}: {value}")
                    
                    # Try multiple date formats and fields
                    pub_date = None
                    
                    # Common Polish date formats
                    date_formats = [
                        '%a, %d %b %Y %H:%M:%S %z',      # RFC 822
                        '%Y-%m-%dT%H:%M:%S%z',           # ISO 8601
                        '%Y-%m-%d %H:%M:%S',
                        '%d.%m.%Y %H:%M:%S',             # Polish format
                        '%d.%m.%Y %H:%M',                # Polish format without seconds
                        '%Y-%m-%d %H:%M',
                        '%d %B %Y %H:%M',                # Polish month names
                        '%d %b %Y %H:%M:%S %z',
                        '%d-%m-%Y %H:%M',
                        '%d/%m/%Y %H:%M'
                    ]
                    
                    # Try all possible date fields
                    date_fields = [
                        'published',
                        'updated',
                        'created',
                        'pubDate',
                        'date',
                        'modified',
                        'dc:date',
                        'lastBuildDate'
                    ]
                    
                    # First try parsed fields
                    for field in ['published_parsed', 'updated_parsed', 'created_parsed']:
                        if hasattr(entry, field):
                            time_struct = getattr(entry, field)
                            if time_struct:
                                pub_date = datetime.fromtimestamp(time.mktime(time_struct))
                                pub_date = pytz.UTC.localize(pub_date)
                                print(f"Found date using {field}: {pub_date}")
                                break
                    
                    # If no parsed date, try string fields
                    if not pub_date:
                        for field in date_fields:
                            if hasattr(entry, field):
                                date_str = getattr(entry, field)
                                print(f"Trying to parse date string: {date_str} from field {field}")
                                for date_format in date_formats:
                                    try:
                                        pub_date = datetime.strptime(date_str, date_format)
                                        if pub_date.tzinfo is None:
                                            pub_date = pytz.UTC.localize(pub_date)
                                        print(f"Successfully parsed date: {pub_date}")
                                        break
                                    except ValueError:
                                        continue
                            if pub_date:
                                break
                    
                    # If still no date, add entry anyway with current time
                    if not pub_date:
                        print(f"Could not parse date for entry: {entry.title}")
                        pub_date = now
                    
                    recent_entries.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': pub_date.strftime('%Y-%m-%d %H:%M:%S UTC'),
                        'description': entry.get('description', 'No description available')
                    })
                
                except Exception as e:
                    print(f"Error processing entry: {str(e)}")
                    continue
            
            return recent_entries
        
        except Exception as e:
            print(f"Error processing feed {feed_url}: {str(e)}")
            return []

    def generate_report(self, urls, processed_sites, failed_sites):
        report_file = os.path.join(self.base_output_dir, f'processing_report_{self.today}.txt')
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("RSS Feed Processing Report\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            # Overall Statistics
            f.write("Overall Statistics:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total websites to process: {len(urls)}\n")
            f.write(f"Successfully processed: {len(processed_sites)}\n")
            f.write(f"Failed to process: {len(failed_sites)}\n")
            f.write(f"Success rate: {(len(processed_sites)/len(urls)*100):.2f}%\n\n")
            
            # Feed Entry Statistics
            f.write("\nFeed Entry Statistics:\n")
            f.write("-" * 40 + "\n")
            total_entries = 0
            for site, feeds in processed_sites.items():
                f.write(f"\nSite: {site}\n")
                site_total = 0
                for feed in feeds:
                    try:
                        feed_data = feedparser.parse(feed)
                        entry_count = len(feed_data.entries)
                        site_total += entry_count
                        f.write(f"- Feed: {feed}\n")
                        f.write(f"  Entries available: {entry_count}\n")
                        if entry_count > 0:
                            latest_entry = feed_data.entries[0]
                            if hasattr(latest_entry, 'published'):
                                f.write(f"  Latest entry date: {latest_entry.published}\n")
                    except Exception as e:
                        f.write(f"- Feed: {feed} (Error reading feed: {str(e)})\n")
                f.write(f"Total entries for this site: {site_total}\n")
                total_entries += site_total
            
            f.write(f"\nTotal entries across all feeds: {total_entries}\n")
            if len(processed_sites) > 0:
                f.write(f"Average entries per site: {total_entries/len(processed_sites):.2f}\n")
            
            # Successfully Processed Sites
            f.write("\nSuccessfully Processed Sites:\n")
            f.write("-" * 40 + "\n")
            for site, feeds in processed_sites.items():
                f.write(f"\nSite: {site}\n")
                f.write(f"Number of feeds found: {len(feeds)}\n")
                f.write("Feeds:\n")
                for feed in feeds:
                    f.write(f"- {feed}\n")
            
            # Failed Sites
            f.write("\n\nFailed Sites:\n")
            f.write("-" * 40 + "\n")
            for site, error in failed_sites:
                f.write(f"\nSite: {site}\n")
                f.write(f"Error: {error}\n")
            
            # Error Analysis
            error_types = {}
            for _, error in failed_sites:
                error_type = str(error).split(':')[0]
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            f.write("\n\nError Analysis:\n")
            f.write("-" * 40 + "\n")
            for error_type, count in error_types.items():
                f.write(f"{error_type}: {count} occurrences\n")
        
        return report_file

    def create_pdf_report(self):
        pdf_file = os.path.join(self.base_output_dir, f'all_news_{self.today}.pdf')
        doc = SimpleDocTemplate(
            pdf_file,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Create styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=20
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=12
        )
        date_style = ParagraphStyle(
            'CustomDate',
            parent=styles['Italic'],
            fontSize=8,
            textColor=colors.gray
        )

        # Build content
        story = []
        
        # Add title
        story.append(Paragraph(f"RSS News Report - {datetime.now().strftime('%Y-%m-%d')}", title_style))
        story.append(Spacer(1, 12))

        # Process each site's folder
        for site_folder in os.listdir(self.base_output_dir):
            site_path = os.path.join(self.base_output_dir, site_folder)
            if os.path.isdir(site_path):
                # Add site header
                story.append(Paragraph(f"Source: {site_folder}", heading_style))
                story.append(Spacer(1, 12))

                # Process news files in the folder
                for file in os.listdir(site_path):
                    if file.startswith('news_') and file.endswith('.txt'):
                        file_path = os.path.join(site_path, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                
                                # Parse and format the content
                                for line in content.split('\n'):
                                    if line.startswith('Title: '):
                                        story.append(Paragraph(line[7:], heading_style))
                                    elif line.startswith('Published: '):
                                        story.append(Paragraph(line, date_style))
                                    elif line.startswith('Link: '):
                                        story.append(Paragraph(f'<link href="{line[6:]}">{line[6:]}</link>', normal_style))
                                    elif line.startswith('Description: '):
                                        story.append(Paragraph(line[13:], normal_style))
                                    elif line.startswith('---'):  # Separator
                                        story.append(Spacer(1, 20))
                        except Exception as e:
                            print(f"Error processing file {file}: {str(e)}")

                # Add page break between sites
                story.append(PageBreak())

        try:
            # Build PDF
            doc.build(story)
            print(f"\nPDF report created: {pdf_file}")
            return pdf_file
        except Exception as e:
            print(f"Error creating PDF: {str(e)}")
            return None

def main():
    finder = RSSFinder()
    finder.process_urls_from_file()

if __name__ == "__main__":
    main() 