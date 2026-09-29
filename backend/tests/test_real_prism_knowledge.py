import unittest
import httpx
from app.rag.schemas.rag import RAGQueryRequest
from app.rag.services.rag_service import default_rag_service


class TestRealPRISMKnowledge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Preserve original inference URL and use deterministic engine for swift assertions
        cls._orig_inference_url = default_rag_service.llm.inference_url
        default_rag_service.llm.inference_url = None

    @classmethod
    def tearDownClass(cls):
        default_rag_service.llm.inference_url = cls._orig_inference_url

    def test_pypdf_pymupdf_trailing_data_differentials(self):
        query = "How do PyPDF and PyMuPDF handle trailing data after the %%EOF marker?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("PyMuPDF" in res.answer or "PyPDF" in res.answer or "EOF" in res.answer)
        self.assertTrue(any("PyMuPDF" in s.title or "PDF" in s.title for s in res.sources))

    def test_zip_local_vs_central_directory_mismatch(self):
        query = "What is a ZIP local header vs central directory mismatch fracture?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("zipfile" in res.answer.lower() or "stream-unzip" in res.answer.lower() or "central directory" in res.answer.lower())
        self.assertTrue(any("zip" in s.title.lower() for s in res.sources))

    def test_prism_minimizer_agent_and_experiments(self):
        query = "How does PRISM minimize a verified fracture-inducing artifact?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("PRISM Lab" in res.answer or "minimization" in res.answer.lower() or "truncate" in res.answer.lower())
        self.assertTrue(any("Minimization" in s.title or "Passport" in s.title or "Experiment" in s.title for s in res.sources))

    def test_pdf_incremental_updates_shadow_attacks(self):
        query = "What causes a boundary disagreement in incremental PDF updates?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("incremental" in res.answer.lower() or "boundary" in res.answer.lower())
        self.assertTrue(any("ISO 32000" in s.title or "PDF" in s.title for s in res.sources))

    def test_semantic_fracture_core_definition(self):
        query = "What is a semantic fracture?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("Semantic Fracture" in res.answer or "disagreement" in res.answer.lower())
        self.assertTrue(any("Semantic Fractures" in s.title for s in res.sources))

    def test_tar_archive_double_zero_eof(self):
        query = "What is the double-zero EOF block requirement in TAR archives?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("512" in res.answer or "double-zero" in res.answer.lower() or "tar" in res.answer.lower())
        self.assertTrue(any("TAR" in s.title for s in res.sources))

    def test_pe_coff_executable_overlay(self):
        query = "How does PE executable overlay handling differ between pefile and Windows loader?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("overlay" in res.answer.lower() or "pe" in res.answer.lower() or "loader" in res.answer.lower())
        self.assertTrue(any("PE" in s.title or "Overlay" in s.title for s in res.sources))

    def test_pefile_vs_lief_differentials(self):
        query = "How do pefile and LIEF differ in virtual size and overlay calculation?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("pefile" in res.answer.lower() or "lief" in res.answer.lower() or "overlay" in res.answer.lower())
        self.assertTrue(any("LIEF" in s.title or "pefile" in s.title for s in res.sources))

    def test_pillow_vs_opencv_differentials(self):
        query = "How do Pillow and OpenCV differ when decoding PNG chunks?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("pillow" in res.answer.lower() or "opencv" in res.answer.lower() or "ancillary" in res.answer.lower() or "idat" in res.answer.lower())
        self.assertTrue(any("Pillow" in s.title or "OpenCV" in s.title or "PNG" in s.title for s in res.sources))

    def test_zip_slip_path_traversal(self):
        query = "What is the Zip Slip path traversal vulnerability?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("traversal" in res.answer.lower() or "zip slip" in res.answer.lower() or "overwrite" in res.answer.lower())
        self.assertTrue(any("Zip Slip" in s.title or "ZIP" in s.title for s in res.sources))

    def test_ghostscript_pdf_postscript_bypass(self):
        query = "How does Ghostscript allow PostScript bypass in PDF documents?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("ghostscript" in res.answer.lower() or "postscript" in res.answer.lower() or "dsafer" in res.answer.lower())
        self.assertTrue(any("Ghostscript" in s.title or "PostScript" in s.title for s in res.sources))

    def test_pe_png_dual_identity_polyglot(self):
        query = "What causes an identity disagreement in PE-PNG polyglots?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("identity_disagreement" in res.answer.lower() or "pe-png" in res.answer.lower() or "polyglot" in res.answer.lower())
        self.assertTrue(any("PE-PNG" in s.title or "Polyglot" in s.title for s in res.sources))

    def test_elf_pyelftools_vs_binfmt_differentials(self):
        query = "How do pyelftools and Linux kernel binfmt differ when section headers are stripped?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("binfmt" in res.answer.lower() or "section" in res.answer.lower() or "pyelftools" in res.answer.lower() or "pt_load" in res.answer.lower())
        self.assertTrue(any("ELF" in s.title or "binfmt" in s.title for s in res.sources))

    def test_macho_java_cafebabe_magic_collision(self):
        query = "What is the 0xCAFEBABE magic collision between Mach-O and Java?"
        res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
        
        self.assertTrue("cafebabe" in res.answer.lower() or "mach-o" in res.answer.lower() or "java" in res.answer.lower())
        self.assertTrue(any("CAFEBABE" in s.title or "Mach-O" in s.title or "Java" in s.title for s in res.sources))

    def test_negative_anti_hallucination_refusal(self):
        query = "What is the capital of France?"
        res = default_rag_service.answer(RAGQueryRequest(question=query))
        
        self.assertIn("does not contain enough information", res.answer)
        self.assertEqual(len(res.sources), 0)

    def test_live_ollama_qwen3_inference(self):
        """Direct end-to-end verification of local Ollama qwen3:4b inference."""
        ollama_url = self._orig_inference_url or "http://localhost:11434"
        try:
            with httpx.Client(timeout=3.0) as client:
                ping = client.get(f"{ollama_url}/api/tags")
                if ping.status_code != 200:
                    self.skipTest("Local Ollama not reachable")
        except Exception:
            self.skipTest("Local Ollama not reachable")

        default_rag_service.llm.inference_url = ollama_url
        try:
            query = "What is the double-zero EOF block requirement in TAR archives?"
            res = default_rag_service.answer(RAGQueryRequest(question=query, include_debug=True))
            self.assertTrue(len(res.answer) > 10)
            self.assertTrue(len(res.sources) > 0)
        finally:
            default_rag_service.llm.inference_url = None


if __name__ == "__main__":
    unittest.main()
