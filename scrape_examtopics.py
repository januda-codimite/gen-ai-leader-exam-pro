#!/usr/bin/env python3
"""
ExamTopics Exam Questions Scraper - Multi-Exam Support
Extracts exam questions from ExamTopics discussions for various certifications.

Supported Exams:
- KCNA (Kubernetes and Cloud Native Associate) - Linux Foundation
- CKA (Certified Kubernetes Administrator) - CNCF
- CKAD (Certified Kubernetes Application Developer) - CNCF
- CKS (Certified Kubernetes Security Specialist) - CNCF
- GAIL (Generative AI Leader) - Google
- PCA (Professional Cloud Architect) - Google

Usage:
    python scrape_examtopics.py --exam cka
    python scrape_examtopics.py --exam kcna
    python scrape_examtopics.py --exam gail --pages 50
    python scrape_examtopics.py --exam pca --pages 178
"""

import requests
from bs4 import BeautifulSoup
import time
import re
import json
import os
import argparse
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class ExamConfig:
    """Configuration for a specific exam"""
    name: str
    full_name: str
    discussion_path: str
    filter_pattern: str
    default_pages: int
    output_file: str


# Exam configurations
EXAM_CONFIGS = {
    'kcna': ExamConfig(
        name='KCNA',
        full_name='Kubernetes and Cloud Native Associate',
        discussion_path='/discussions/linux-foundation/',
        filter_pattern='KCNA',
        default_pages=17,
        output_file='kcna_exam_questions.md'
    ),
    'cka': ExamConfig(
        name='CKA',
        full_name='Certified Kubernetes Administrator',
        discussion_path='/discussions/cncf/',
        filter_pattern='CKA',
        default_pages=5,  # Will auto-detect actual pages
        output_file='cka_exam_questions.md'
    ),
    'ckad': ExamConfig(
        name='CKAD',
        full_name='Certified Kubernetes Application Developer',
        discussion_path='/discussions/cncf/',
        filter_pattern='CKAD',
        default_pages=5,
        output_file='ckad_exam_questions.md'
    ),
    'cks': ExamConfig(
        name='CKS',
        full_name='Certified Kubernetes Security Specialist',
        discussion_path='/discussions/cncf/',
        filter_pattern='CKS',
        default_pages=5,
        output_file='cks_exam_questions.md'
    ),
    'gail': ExamConfig(
        name='GAIL',
        full_name='Google Generative AI Leader',
        discussion_path='/discussions/google/',
        filter_pattern='Generative AI Leader',
        default_pages=174,  # Google has many pages, will auto-detect
        output_file='gail_exam_questions.md'
    ),
    'pca': ExamConfig(
        name='PCA',
        full_name='Google Professional Cloud Architect',
        discussion_path='/discussions/google/',
        filter_pattern='Professional Cloud Architect',
        default_pages=178,  # Google has many pages, will auto-detect
        output_file='pca_exam_questions.md'
    )
}


class ExamTopicsScraper:
    def __init__(self, exam_config: ExamConfig, delay: float = 1.5, progress_file: str = None):
        """
        Initialize scraper with exam configuration and rate limiting
        
        Args:
            exam_config: Configuration for the target exam
            delay: Delay in seconds between requests (default: 1.5)
            progress_file: File to save progress (auto-generated if None)
        """
        self.base_url = "https://www.examtopics.com"
        self.config = exam_config
        self.delay = delay
        self.progress_file = progress_file or f"scrape_progress_{exam_config.name.lower()}.json"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with error handling"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            time.sleep(self.delay)
            return BeautifulSoup(response.text, 'lxml')
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def save_progress(self, data: Dict):
        """Save progress to JSON file"""
        with open(self.progress_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_progress(self) -> Optional[Dict]:
        """Load progress from JSON file"""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return None
    
    def get_total_pages(self) -> int:
        """Detect total number of discussion pages"""
        url = f"{self.base_url}{self.config.discussion_path}"
        soup = self._get_page(url)
        
        if not soup:
            return self.config.default_pages
        
        # Look for pagination info: "Page X of Y"
        page_indicator = soup.find('span', class_='discussion-list-page-indicator')
        if page_indicator:
            text = page_indicator.get_text()
            match = re.search(r'of\s*<strong>(\d+)</strong>', str(page_indicator))
            if match:
                return int(match.group(1))
            # Alternative pattern
            match = re.search(r'of\s+(\d+)', text)
            if match:
                return int(match.group(1))
        
        return self.config.default_pages
    
    def get_discussion_urls(self, num_pages: int = None) -> List[Dict[str, str]]:
        """Scrape all discussion pages and extract exam-specific links"""
        if num_pages is None:
            num_pages = self.get_total_pages()
        
        all_discussions = []
        
        print(f"Collecting {self.config.name} discussion URLs from {num_pages} pages...")
        
        for page in range(1, num_pages + 1):
            url = f"{self.base_url}{self.config.discussion_path}{page}/"
            print(f"  Scanning page {page}/{num_pages}...", end=' ')
            soup = self._get_page(url)
            
            if not soup:
                print("failed")
                continue
            
            # Find all discussion links
            links = soup.find_all('a', class_='discussion-link')
            page_count = 0
            
            for link in links:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                # Filter for target exam only
                if self.config.filter_pattern.upper() in title.upper():
                    # Extract question and topic number from title
                    topic_match = re.search(r'topic\s+(\d+)', title, re.IGNORECASE)
                    question_match = re.search(r'question\s+(\d+)', title, re.IGNORECASE)
                    
                    topic_num = topic_match.group(1) if topic_match else '1'
                    question_num = question_match.group(1) if question_match else 'unknown'
                    
                    all_discussions.append({
                        'title': title,
                        'url': self.base_url + href if href.startswith('/') else href,
                        'topic_num': topic_num,
                        'question_num': question_num
                    })
                    page_count += 1
            
            print(f"found {page_count} {self.config.name} discussions")
        
        # Remove duplicates based on URL
        seen = set()
        unique = []
        for d in all_discussions:
            if d['url'] not in seen:
                unique.append(d)
                seen.add(d['url'])
        
        # Sort by topic and question number
        unique.sort(key=lambda x: (
            int(x['topic_num']) if x['topic_num'].isdigit() else 999,
            int(x['question_num']) if x['question_num'].isdigit() else 999999
        ))
        
        print(f"\nTotal: {len(unique)} unique {self.config.name} discussions found\n")
        return unique
    
    def extract_question(self, url: str) -> Optional[Dict]:
        """Extract question data from discussion page"""
        soup = self._get_page(url)
        if not soup:
            return None

        try:
            question_text = ""
            options = []
            correct_letters = []
            most_voted = ""

            # Extract question from question-body div
            question_body = soup.find('div', class_='question-body')
            if question_body:
                card_text = question_body.find('p', class_='card-text')
                if card_text:
                    # Get HTML content and convert to text
                    question_html = str(card_text)

                    # Replace <br> with newlines
                    question_html = re.sub(r'<br\s*/?>', '\n', question_html)

                    # Extract images
                    images = card_text.find_all('img')
                    image_urls = [img.get('src', '') for img in images if img.get('src')]

                    # Remove HTML tags for clean text
                    clean_soup = BeautifulSoup(question_html, 'lxml')
                    question_text = clean_soup.get_text(separator='\n').strip()

                    # Add image references if present
                    if image_urls:
                        question_text += "\n\n**Images:**\n"
                        for i, img_url in enumerate(image_urls, 1):
                            if not img_url.startswith('http'):
                                img_url = self.base_url + img_url
                            question_text += f"- ![Image {i}]({img_url})\n"

                # Extract answer choices (current ExamTopics template)
                choices_container = question_body.find('div', class_='question-choices-container')
                if choices_container:
                    for li in choices_container.find_all('li', class_='multi-choice-item'):
                        li_copy = BeautifulSoup(str(li), 'lxml')
                        letter_span = li_copy.find('span', class_='multi-choice-letter')
                        letter = letter_span.get('data-choice-letter', '') if letter_span else ''
                        if letter_span:
                            letter_span.decompose()
                        options.append(li_copy.get_text(strip=True))
                        if 'correct-hidden' in li.get('class', []):
                            correct_letters.append(letter)

                # Extract community-voted answer as a fallback/cross-check
                tally = question_body.find('div', class_='voted-answers-tally')
                if tally:
                    script_tag = tally.find('script')
                    if script_tag and script_tag.string:
                        try:
                            tally_data = json.loads(script_tag.string)
                            entry = next((t for t in tally_data if t.get('is_most_voted')), tally_data[0] if tally_data else None)
                            if entry:
                                most_voted = entry.get('voted_answers', '')
                        except (json.JSONDecodeError, IndexError, StopIteration):
                            pass

            # Extract highly voted comments for additional context
            highly_voted = []
            comments = soup.find_all('div', class_='comment-container')
            for comment in comments[:3]:  # Get top 3 comments
                badge = comment.find('span', class_='badge-primary')
                if badge and 'Highly Voted' in badge.get_text():
                    content_div = comment.find('div', class_='comment-content')
                    if content_div:
                        upvotes = comment.find('span', class_='upvote-count')
                        upvote_count = upvotes.get_text(strip=True) if upvotes else '0'
                        highly_voted.append({
                            'content': content_div.get_text(strip=True)[:1500],  # Limit length
                            'upvotes': upvote_count
                        })

            return {
                'question': question_text or "Question text not extracted",
                'options': options,
                'correct_letters': correct_letters,
                'most_voted': most_voted,
                'highly_voted_comments': highly_voted,
                'url': url
            }

        except Exception as e:
            print(f"Parse error for {url}: {e}")
            return None
    
    def scrape_all(self, num_pages: int = None) -> List[Dict]:
        """Main scraping method with progress saving"""
        # Try to resume from progress
        progress = self.load_progress()
        
        if progress and progress.get('exam') == self.config.name and 'discussions' in progress:
            print("Resuming from saved progress...")
            discussions = progress['discussions']
            questions_data = progress.get('questions_data', [])
            start_idx = len(questions_data)
        else:
            discussions = self.get_discussion_urls(num_pages)
            questions_data = []
            start_idx = 0
            # Save initial progress
            self.save_progress({
                'exam': self.config.name,
                'discussions': discussions,
                'questions_data': []
            })
        
        total = len(discussions)
        if start_idx >= total:
            print("All questions already extracted!")
            return questions_data
        
        print(f"Extracting questions ({start_idx + 1}/{total})...\n")
        
        for i in range(start_idx, total):
            disc = discussions[i]
            q_num = f"T{disc['topic_num']}-Q{disc['question_num']}"
            print(f"[{i+1}/{total}] {q_num}", end=' ')
            
            q_data = self.extract_question(disc['url'])
            
            if q_data:
                q_data['topic_num'] = disc['topic_num']
                q_data['question_num'] = disc['question_num']
                q_data['title'] = disc['title']
                questions_data.append(q_data)
                print("OK")
            else:
                print("FAILED")
            
            # Save progress every 5 questions
            if (i + 1) % 5 == 0:
                self.save_progress({
                    'exam': self.config.name,
                    'discussions': discussions,
                    'questions_data': questions_data
                })
        
        # Final save
        self.save_progress({
            'exam': self.config.name,
            'discussions': discussions,
            'questions_data': questions_data
        })
        
        print(f"\nExtracted {len(questions_data)}/{total} questions")
        return questions_data
    
    def generate_markdown(self, questions_data: List[Dict], output: str = None):
        """Generate markdown file with all questions"""
        output = output or self.config.output_file
        print(f"\nGenerating {output}...")
        
        with open(output, 'w', encoding='utf-8') as f:
            # Header
            f.write(f"# {self.config.name} Exam Questions - ExamTopics\n\n")
            f.write(f"**Exam:** {self.config.full_name} ({self.config.name})\n\n")
            f.write(f"**Total Questions:** {len(questions_data)}\n\n")
            f.write(f"**Source:** ExamTopics Discussion Forum\n\n")
            f.write(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            
            # Table of Contents
            f.write("## Table of Contents\n\n")
            current_topic = None
            for q in questions_data:
                topic = q.get('topic_num', '1')
                num = q.get('question_num', 'N/A')
                if topic != current_topic:
                    f.write(f"\n### Topic {topic}\n\n")
                    current_topic = topic
                f.write(f"- [Question {num}](#topic-{topic}-question-{num})\n")
            f.write("\n---\n\n")
            
            # Questions
            letters = 'ABCDEFGH'
            for q in questions_data:
                topic = q.get('topic_num', '1')
                num = q.get('question_num', 'N/A')
                question = q.get('question', 'N/A')
                options = q.get('options', [])
                correct_letters = q.get('correct_letters', [])
                most_voted = q.get('most_voted', '')
                url = q.get('url', '')
                highly_voted = q.get('highly_voted_comments', [])

                f.write(f"## Topic {topic} Question {num}\n\n")

                # Question text
                f.write(f"**Question:** {question}\n\n")

                # Answer choices
                for i, opt in enumerate(options):
                    if i < len(letters):
                        f.write(f"**{letters[i]}.** {opt}\n")
                f.write("\n")

                # Correct answer
                if correct_letters:
                    f.write(f"**Correct Answer: {''.join(correct_letters)}**\n\n")
                elif most_voted:
                    f.write(f"**Correct Answer: {most_voted}** *(highest community vote — not vendor-confirmed)*\n\n")
                else:
                    f.write(f"**Correct Answer: Not specified**\n\n")

                # Description sourced from the top community explanation
                if highly_voted:
                    f.write(f"**Description:** {highly_voted[0]['content']}\n\n")

                # Additional community answers
                if len(highly_voted) > 1:
                    f.write(f"### Top Community Answers\n\n")
                    for idx, comment in enumerate(highly_voted[1:], 2):
                        f.write(f"**Comment {idx}** (Upvotes: {comment['upvotes']})\n")
                        f.write(f"> {comment['content']}\n\n")

                # Source link
                f.write(f"**Discussion:** [View on ExamTopics]({url})\n\n")
                f.write("---\n\n")
        
        print(f"Generated: {output}")
        
        # Show file stats
        file_size = os.path.getsize(output)
        with open(output, 'r') as f:
            line_count = sum(1 for _ in f)
        print(f"  - {line_count} lines")
        print(f"  - {file_size / 1024:.1f} KB")


def main():
    """Main execution with command-line arguments"""
    parser = argparse.ArgumentParser(
        description='ExamTopics Exam Questions Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape_examtopics.py --exam cka
  python scrape_examtopics.py --exam kcna --pages 17
  python scrape_examtopics.py --exam gail --delay 2.0

Supported exams: kcna, cka, ckad, cks, gail (Generative AI Leader)
        """
    )
    
    parser.add_argument(
        '--exam', '-e',
        type=str,
        required=True,
        choices=list(EXAM_CONFIGS.keys()),
        help='Exam to scrape (kcna, cka, ckad, cks, gail, pca)'
    )
    
    parser.add_argument(
        '--pages', '-p',
        type=int,
        default=None,
        help='Number of discussion pages to scan (auto-detected if not specified)'
    )
    
    parser.add_argument(
        '--delay', '-d',
        type=float,
        default=1.5,
        help='Delay between requests in seconds (default: 1.5)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output markdown filename (default: {exam}_exam_questions.md)'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clear previous progress and start fresh'
    )
    
    args = parser.parse_args()
    
    # Get exam configuration
    exam_config = EXAM_CONFIGS[args.exam.lower()]
    
    print("=" * 60)
    print(f"ExamTopics {exam_config.name} Questions Scraper")
    print(f"{exam_config.full_name}")
    print("=" * 60)
    print()
    
    # Initialize scraper
    scraper = ExamTopicsScraper(exam_config, delay=args.delay)
    
    # Clean progress if requested
    if args.clean and os.path.exists(scraper.progress_file):
        os.remove(scraper.progress_file)
        print("Cleared previous progress.\n")
    
    # Scrape questions
    questions = scraper.scrape_all(num_pages=args.pages)
    
    if questions:
        # Generate markdown
        output_file = args.output or exam_config.output_file
        scraper.generate_markdown(questions, output_file)
        
        # Cleanup progress file on success
        if os.path.exists(scraper.progress_file):
            os.remove(scraper.progress_file)
        
        print("\n" + "=" * 60)
        print(f"Scraping completed successfully!")
        print(f"Output: {output_file}")
        print("=" * 60)
    else:
        print("\nNo questions extracted. Check errors above.")


if __name__ == "__main__":
    main()
