"""Storage Watcher Service.

This service monitors storage systems (local, S3, GCS) for changes and
publishes notifications to RabbitMQ when new files are detected.
"""