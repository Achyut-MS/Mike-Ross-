"""
Django management command to ingest legal knowledge into ChromaDB.

Usage:
    python manage.py ingest_knowledge
    python manage.py ingest_knowledge --clear   # Clear and re-ingest
    python manage.py ingest_knowledge --stats    # Show stats only
"""

from django.core.management.base import BaseCommand

from cases.knowledge_base import KnowledgeBaseManager


class Command(BaseCommand):
    help = 'Ingest legal knowledge base into ChromaDB for RAG retrieval'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing knowledge base before ingesting',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show knowledge base statistics only',
        )

    def handle(self, *args, **options):
        kb = KnowledgeBaseManager()

        if options['stats']:
            stats = kb.get_stats()
            self.stdout.write(self.style.SUCCESS(
                f"Collection: {stats['collection_name']}\n"
                f"Total chunks: {stats['total_chunks']}\n"
                f"Persist dir: {stats['persist_directory']}"
            ))
            return

        if options['clear']:
            self.stdout.write('Clearing existing knowledge base...')
            kb.clear()

        self.stdout.write('Ingesting legal knowledge...')
        result = kb.ingest_all()

        self.stdout.write(self.style.SUCCESS(
            f"\nIngestion complete!\n"
            f"  Documents: {result['documents_ingested']}\n"
            f"  Chunks: {result['chunks_created']}\n"
            f"  Total in collection: {result['collection_count']}"
        ))

        # Quick search test
        self.stdout.write('\nRunning test search: "security deposit return Karnataka"')
        texts, scores, metas = kb.search('security deposit return Karnataka', top_k=3)

        for i, (text, score, meta) in enumerate(zip(texts, scores, metas)):
            self.stdout.write(self.style.HTTP_INFO(
                f"\n  [{i+1}] Score: {score:.3f}\n"
                f"      Source: {meta['source']} — {meta['section']}\n"
                f"      Text: {text[:120]}..."
            ))
