#!/usr/bin/env python
"""
Quick test untuk Indonesian language support
"""

import sys
sys.path.insert(0, '/app')

from app.services.custom_nlp import (
    detect_language,
    preprocess_indonesian_text,
    extract_keywords_indonesian,
    remove_indonesian_stopwords,
    create_extractive_summary_indonesian
)

def test_language_detection():
    """Test language detection"""
    print("\n=== Testing Language Detection ===")
    
    # Indonesian text
    text_id = "Penelitian ini menggunakan machine learning untuk mengklasifikasi dokumen bahasa Indonesia dengan akurasi tinggi."
    lang = detect_language(text_id)
    print(f"✅ Indonesian text detected as: {lang}")
    assert lang == 'id', "Failed to detect Indonesian"
    
    # English text
    text_en = "This research uses machine learning for document classification with high accuracy."
    lang = detect_language(text_en)
    print(f"✅ English text detected as: {lang}")
    assert lang == 'en', "Failed to detect English"
    
    print("✓ Language detection: PASSED")

def test_stopwords():
    """Test stopwords removal"""
    print("\n=== Testing Stopwords ===")
    
    tokens = ['penelitian', 'dan', 'machine', 'learning', 'dengan', 'akurasi', 'tinggi']
    cleaned = remove_indonesian_stopwords(tokens)
    print(f"Original: {tokens}")
    print(f"Cleaned: {cleaned}")
    
    # Should remove 'dan' and 'dengan'
    assert 'dan' not in cleaned, "Failed to remove 'dan'"
    assert 'dengan' not in cleaned, "Failed to remove 'dengan'"
    assert 'penelitian' in cleaned, "Removed wrong word"
    assert 'machine' in cleaned, "Removed wrong word"
    
    print("✓ Stopwords removal: PASSED")

def test_preprocessing():
    """Test text preprocessing"""
    print("\n=== Testing Text Preprocessing ===")
    
    text = "Teks   dengan    spasi    berlebih\n\ndan newline"
    clean = preprocess_indonesian_text(text)
    print(f"Original: {repr(text)}")
    print(f"Cleaned: {repr(clean)}")
    
    # Should normalize spaces
    assert '   ' not in clean, "Spaces not normalized"
    
    print("✓ Text preprocessing: PASSED")

def test_keyword_extraction():
    """Test keyword extraction"""
    print("\n=== Testing Keyword Extraction ===")
    
    text = """
    Penelitian ini menggunakan machine learning dan deep learning untuk klasifikasi dokumen.
    Machine learning adalah teknologi penting dalam pengolahan bahasa alami.
    Hasil penelitian menunjukkan bahwa deep learning memberikan akurasi lebih tinggi.
    """
    
    keywords = extract_keywords_indonesian(text, top_n=5)
    print(f"Top 5 keywords: {keywords}")
    
    # Should extract relevant keywords
    assert len(keywords) > 0, "No keywords extracted"
    assert len(keywords) <= 5, "Too many keywords extracted"
    
    # Should contain domain-related words
    assert any(kw in keywords for kw in ['machine', 'learning', 'deep', 'klasifikasi', 'penelitian']), \
        f"Expected keywords not found in: {keywords}"
    
    print("✓ Keyword extraction: PASSED")

def test_summary_generation():
    """Test extractive summary generation"""
    print("\n=== Testing Summary Generation ===")
    
    text = """
    Kalimat pertama membahas tentang machine learning dan aplikasinya yang sangat luas.
    Kalimat kedua menjelaskan bahwa machine learning membutuhkan data yang banyak untuk training.
    Kalimat ketiga menyatakan bahwa hasil machine learning sangat bergantung pada kualitas data.
    Kalimat keempat menunjukkan bahwa machine learning telah digunakan di banyak industri.
    Kalimat kelima membahas tantangan utama dalam implementasi machine learning di praktik nyata.
    """
    
    summary = create_extractive_summary_indonesian(text, num_sentences=2)
    print(f"Original text ({len(text)} chars)")
    print(f"Summary ({len(summary)} chars):\n{summary}")
    
    # Summary should be shorter than original
    assert len(summary) < len(text), "Summary not shorter than original"
    
    # Summary should contain complete sentences
    assert '.' in summary, "Summary doesn't contain proper sentences"
    
    print("✓ Summary generation: PASSED")

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*50)
    print("🧪 Indonesian Language Support - Test Suite")
    print("="*50)
    
    try:
        test_language_detection()
        test_stopwords()
        test_preprocessing()
        test_keyword_extraction()
        test_summary_generation()
        
        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("="*50)
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
