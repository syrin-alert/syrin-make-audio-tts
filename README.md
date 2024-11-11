# syrin-make-audio-tts

The `syrin-make-audio-tts` component generates and manages humanized audio notifications. It integrates with RabbitMQ, MinIO, and uses Coqui TTS for text-to-speech synthesis, allowing messages to be processed, saved, and delivered as audio.

## Demo

![Application Demo](./driagrams/Syrin-Make-Audio-TTS.gif)

## Table of Contents
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Functionality](#functionality)
- [Queue Declarations](#queue-declarations)
- [Logging](#logging)
- [License](#license)

## Installation

Ensure that RabbitMQ, MinIO, and Coqui TTS are configured and accessible. For full installation details, refer to the [SYRIN Installation Repository](https://github.com/syrin-alert/syrin-install).

## Environment Variables

Set the following environment variables to configure RabbitMQ, MinIO, and TTS settings:

### RabbitMQ Settings

- `RABBITMQ_HOST`: RabbitMQ server address.
- `RABBITMQ_PORT`: Port for RabbitMQ server (default: `5672`).
- `RABBITMQ_VHOST`: Virtual host in RabbitMQ.
- `RABBITMQ_USER`: Username for RabbitMQ authentication.
- `RABBITMQ_PASS`: Password for RabbitMQ authentication.
- `RABBITMQ_TTL_DLX`: Time-to-live in ms for dead-letter queue (default: `60000`).

### MinIO Settings

- `MINIO_URL`: MinIO server URL.
- `MINIO_PORT`: Port for MinIO server (default: `9000`).
- `MINIO_ROOT_USER`: Username for MinIO authentication.
- `MINIO_ROOT_PASSWORD`: Password for MinIO authentication.
- `MINIO_BUCKET_WORK`: Bucket name for storing audio files.

### TTS Settings

- `TTS_LANGUAGE`: Language for TTS synthesis (default: `pt-br`).
- `TTS_EMOTION`: Emotion for the TTS output (e.g., "happy", "neutral").
- `TTS_SPEED_VOICE`: Speed adjustment for the TTS voice (e.g., 0.8 or 1.1).
- `TTS_PATH_CLONE_AUDIO`: Path to the reference audio for voice cloning.
- `TTS_MODEL`: Model name for Coqui TTS (default: `tts_models/multilingual/multi-dataset/your_tts`).

## Functionality

This script performs the following tasks:

1. Connects to RabbitMQ, MinIO, and Coqui TTS based on provided environment settings.
2. Processes messages from queues, generates humanized audio using TTS, and uploads files to MinIO.
3. Routes messages for playback or reprocessing based on success or failure of operations.

### Queue Declarations

The following queues are managed in RabbitMQ:

- `02_syrin_notification_audio_process_humanized`: Processes humanized audio notifications.
- `02_syrin_notification_audio_reprocess_humanized`: Handles reprocessing for failed notifications.
- `03_syrin_notification_audio_process_play`: Sends processed notifications for audio playback.

## Logging

Logging is set at the INFO level with `pika` logs set to WARNING to reduce verbosity.

## License

This project is licensed under the MIT License.