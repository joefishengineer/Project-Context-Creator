"""
Conversion Quality Checker
Validates markdown conversions and detects quality issues
"""

from pathlib import Path
import logging
import re

class ConversionQuality:
    """Represents the quality assessment of a conversion"""
    
    def __init__(self, source_path, output_path):
        self.source_path = Path(source_path)
        self.output_path = Path(output_path) if output_path else None
        self.issues = []
        self.warnings = []
        self.metrics = {}
        self.quality_score = 0.0
        self.status = "UNKNOWN"
    
    def add_issue(self, issue):
        """Add a critical issue"""
        self.issues.append(issue)
        logging.error(f"Quality Issue: {issue}")
    
    def add_warning(self, warning):
        """Add a warning"""
        self.warnings.append(warning)
        logging.warning(f"Quality Warning: {warning}")
    
    def calculate_score(self):
        """Calculate overall quality score (0-100)"""
        score = 100.0
        
        # Critical issues
        score -= len(self.issues) * 25  # Each issue -25 points
        
        # Warnings
        score -= len(self.warnings) * 5  # Each warning -5 points
        
        # Bonus for good metrics
        if self.metrics.get('word_count', 0) > 100:
            score += 5
        if self.metrics.get('compression_ratio', 0) < 50:  # Good compression
            score += 5
        
        self.quality_score = max(0.0, min(100.0, score))
        
        # Determine status
        if self.quality_score >= 80:
            self.status = "EXCELLENT"
        elif self.quality_score >= 60:
            self.status = "GOOD"
        elif self.quality_score >= 40:
            self.status = "FAIR"
        elif self.quality_score >= 20:
            self.status = "POOR"
        else:
            self.status = "FAILED"
        
        return self.quality_score
    
    def get_report(self):
        """Generate a quality report"""
        lines = []
        lines.append(f"\n{'='*60}")
        lines.append(f"Quality Report: {self.source_path.name}")
        lines.append(f"{'='*60}")
        lines.append(f"Status: {self.status}")
        lines.append(f"Quality Score: {self.quality_score:.1f}/100")
        lines.append(f"\nMetrics:")
        for key, value in self.metrics.items():
            lines.append(f"  {key}: {value}")
        
        if self.issues:
            lines.append(f"\n❌ Critical Issues ({len(self.issues)}):")
            for issue in self.issues:
                lines.append(f"  - {issue}")
        
        if self.warnings:
            lines.append(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
        
        if not self.issues and not self.warnings:
            lines.append(f"\n✅ No issues detected")
        
        lines.append(f"{'='*60}\n")
        return '\n'.join(lines)


def check_conversion_quality(source_path, output_path):
    """
    Check the quality of a conversion.
    
    Args:
        source_path: Path to source file
        output_path: Path to converted markdown file
    
    Returns:
        ConversionQuality object with assessment
    """
    quality = ConversionQuality(source_path, output_path)
    
    source_path = Path(source_path)
    output_path = Path(output_path) if output_path else None
    
    # Check if source exists
    if not source_path.exists():
        quality.add_issue(f"Source file not found: {source_path}")
        quality.calculate_score()
        return quality
    
    # Check if output exists
    if not output_path or not output_path.exists():
        quality.add_issue(f"Output file not created")
        quality.calculate_score()
        return quality
    
    # Get file sizes
    source_size = source_path.stat().st_size
    output_size = output_path.stat().st_size
    
    quality.metrics['source_size_kb'] = round(source_size / 1024, 2)
    quality.metrics['output_size_kb'] = round(output_size / 1024, 2)
    
    # Check for empty or near-empty output
    if output_size < 100:  # Less than 100 bytes
        quality.add_issue("Output file is essentially empty (< 100 bytes)")
    elif output_size < 500:  # Less than 500 bytes
        quality.add_warning("Output file is very small (< 500 bytes)")
    
    # Read and analyze output content
    try:
        content = output_path.read_text(encoding='utf-8')
        
        # Count meaningful content
        lines = content.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]
        
        # Remove header lines
        content_lines = [l for l in non_empty_lines 
                        if not l.startswith('#') 
                        and not l.startswith('*Converted from:')
                        and not l.startswith('---')
                        and not l.strip() == '']
        
        quality.metrics['total_lines'] = len(lines)
        quality.metrics['content_lines'] = len(content_lines)
        
        # Count words
        words = re.findall(r'\b\w+\b', content)
        quality.metrics['word_count'] = len(words)
        
        # Check for placeholder text indicating failed extraction
        placeholder_patterns = [
            r'\*\[No text content\]',
            r'\*\[No text content extracted\]',
            r'--',  # Common placeholder in tables
        ]
        
        placeholder_count = 0
        for pattern in placeholder_patterns:
            placeholder_count += len(re.findall(pattern, content))
        
        if placeholder_count > 10:
            quality.add_warning(f"High number of placeholders ({placeholder_count}) - possible extraction issues")
        
        # Check for suspiciously low word count
        if quality.metrics['word_count'] < 50:
            quality.add_issue(f"Very low word count ({quality.metrics['word_count']}) - likely failed extraction")
        elif quality.metrics['word_count'] < 200:
            quality.add_warning(f"Low word count ({quality.metrics['word_count']}) - possible incomplete extraction")
        
        # Check compression ratio
        if source_size > 0:
            compression_ratio = ((source_size - output_size) / source_size) * 100
            quality.metrics['compression_ratio'] = round(compression_ratio, 2)
            
            # Extreme compression might indicate data loss
            if compression_ratio > 99.5:
                quality.add_issue(f"Extreme compression ({compression_ratio:.2f}%) - likely data loss")
            elif compression_ratio > 99:
                quality.add_warning(f"Very high compression ({compression_ratio:.2f}%) - check for data loss")
        
        # Check for missing words pattern (common in PPTX issues)
        # Look for patterns like "word  word" (double space) or "word [?] word"
        double_spaces = len(re.findall(r'\w\s{2,}\w', content))
        if double_spaces > 20:
            quality.add_warning(f"Many double spaces ({double_spaces}) - possible missing words")
        
        # Check content density (words per line)
        if len(content_lines) > 0:
            words_per_line = quality.metrics['word_count'] / len(content_lines)
            quality.metrics['words_per_line'] = round(words_per_line, 2)
            
            if words_per_line < 3:
                quality.add_warning(f"Low content density ({words_per_line:.1f} words/line) - fragmented extraction")
        
    except Exception as e:
        quality.add_issue(f"Failed to analyze output content: {e}")
    
    # Calculate final score
    quality.calculate_score()
    
    return quality


def batch_quality_check(conversions):
    """
    Check quality for multiple conversions.
    
    Args:
        conversions: List of (source_path, output_path) tuples
    
    Returns:
        Dictionary with summary statistics and list of quality objects
    """
    results = []
    
    for source_path, output_path in conversions:
        quality = check_conversion_quality(source_path, output_path)
        results.append(quality)
    
    # Generate summary
    summary = {
        'total': len(results),
        'excellent': sum(1 for q in results if q.status == 'EXCELLENT'),
        'good': sum(1 for q in results if q.status == 'GOOD'),
        'fair': sum(1 for q in results if q.status == 'FAIR'),
        'poor': sum(1 for q in results if q.status == 'POOR'),
        'failed': sum(1 for q in results if q.status == 'FAILED'),
        'avg_score': sum(q.quality_score for q in results) / len(results) if results else 0,
        'total_issues': sum(len(q.issues) for q in results),
        'total_warnings': sum(len(q.warnings) for q in results),
    }
    
    return {
        'summary': summary,
        'results': results
    }


def generate_quality_report(batch_results, output_path=None):
    """Generate a comprehensive quality report"""
    summary = batch_results['summary']
    results = batch_results['results']
    
    lines = []
    lines.append("="*80)
    lines.append("CONVERSION QUALITY REPORT")
    lines.append("="*80)
    lines.append(f"\nTotal Conversions: {summary['total']}")
    lines.append(f"Average Quality Score: {summary['avg_score']:.1f}/100")
    lines.append(f"\nStatus Breakdown:")
    lines.append(f"  ✅ Excellent: {summary['excellent']} ({summary['excellent']/summary['total']*100:.1f}%)")
    lines.append(f"  ✓  Good: {summary['good']} ({summary['good']/summary['total']*100:.1f}%)")
    lines.append(f"  ~  Fair: {summary['fair']} ({summary['fair']/summary['total']*100:.1f}%)")
    lines.append(f"  ⚠  Poor: {summary['poor']} ({summary['poor']/summary['total']*100:.1f}%)")
    lines.append(f"  ❌ Failed: {summary['failed']} ({summary['failed']/summary['total']*100:.1f}%)")
    lines.append(f"\nTotal Issues: {summary['total_issues']}")
    lines.append(f"Total Warnings: {summary['total_warnings']}")
    
    # List problematic files
    problematic = [q for q in results if q.status in ['POOR', 'FAILED']]
    if problematic:
        lines.append(f"\n{'='*80}")
        lines.append(f"PROBLEMATIC FILES ({len(problematic)}):")
        lines.append(f"{'='*80}")
        for q in problematic:
            lines.append(f"\n{q.source_path.name}")
            lines.append(f"  Status: {q.status} (Score: {q.quality_score:.1f})")
            if q.issues:
                lines.append(f"  Issues: {', '.join(q.issues[:2])}")
    
    report = '\n'.join(lines)
    
    if output_path:
        Path(output_path).write_text(report, encoding='utf-8')
        logging.info(f"Quality report saved to: {output_path}")
    
    return report


# Made with Bob