import os
import pika
import json
import logging
import torch
from datetime import datetime
from minio import Minio
from minio.error import S3Error
from TTS.api import TTS  # Coqui TTS Library
os.environ["COQUI_TOS_AGREED"] = "1"

# Set log level to INFO
logging.basicConfig(level=logging.INFO)

# Disable debug logs from pika by setting it to WARNING or higher
logging.getLogger("pika").setLevel(logging.WARNING)

# Verificar se a GPU está disponível e definir o dispositivo
device = "cuda" if torch.cuda.is_available() else "cpu"

# Load the YourTTS model from Coqui (multilingual)
# TTS CONFIGS
tts_language = os.getenv('TTS_LANGUAGE', 'pt-br') # pt-br, en and etc...
tts_emotion = os.getenv('TTS_EMOTION', 'happy') # (ex: "neutral", "happy", "surprise" "sad", "angry")
tts_speed_voice = float(os.getenv('TTS_SPEED_VOICE', 1)) # Ajuste de velocidade, pode testar valores como 0.8 ou 1.1
tts_path_clone_audio = os.getenv('TTS_PATH_CLONE_AUDIO', '/app/YOUR-AUDIO-VOICE.wav') #/app/veicaetano.wav
tts_model = os.getenv('TTS_MODEL', 'tts_models/multilingual/multi-dataset/your_tts') #
tts = TTS(model_name=tts_model, progress_bar=True)
tts.to(device)  # Definir o dispositivo para o modelo

# Load RabbitMQ settings from environment variables
rabbitmq_host = os.getenv('RABBITMQ_HOST', '')
rabbitmq_port = int(os.getenv('RABBITMQ_PORT', 5672))
rabbitmq_vhost = os.getenv('RABBITMQ_VHOST', '')
rabbitmq_user = os.getenv('RABBITMQ_USER', '')
rabbitmq_pass = os.getenv('RABBITMQ_PASS', '')
# TTL and DLX settings for reprocessing
rabbitmq_ttl_dlx = int(os.getenv('RABBITMQ_TTL_DLX', 60000))  # 60 seconds TTL (60000 ms)


# Load MinIO settings from environment variables
MINIO_URL = os.getenv('MINIO_URL', '')
MINIO_PORT = int(os.getenv('MINIO_PORT', 9000))
MINIO_ROOT_USER = os.getenv('MINIO_ROOT_USER', '')
MINIO_ROOT_PASSWORD = os.getenv('MINIO_ROOT_PASSWORD', '')
MINIO_BUCKET_WORK = os.getenv('MINIO_BUCKET_WORK', 'syrin')

# Connect to MinIO
minio_client = Minio(
    f"{MINIO_URL}:{MINIO_PORT}",
    access_key=MINIO_ROOT_USER,
    secret_key=MINIO_ROOT_PASSWORD,
    secure=False
)

# Function to upload the file to MinIO
def upload_to_minio(file_path, file_name):
    try:
        # Check if the bucket exists, if not, create it
        if not minio_client.bucket_exists(MINIO_BUCKET_WORK):
            minio_client.make_bucket(MINIO_BUCKET_WORK)
        
        # Upload the file
        minio_client.fput_object(
            MINIO_BUCKET_WORK, 
            file_name, 
            file_path,
            content_type="audio/wav"
        )
        logging.info(f"File {file_name} uploaded to bucket {MINIO_BUCKET_WORK} on MinIO.")
        return True
    except S3Error as e:
        logging.error(f"Error uploading file to MinIO: {str(e)}")
        return False

def delete_local_file(file_path):
    try:
        os.remove(file_path)
        logging.info(f"Local file {file_path} successfully deleted.")
    except OSError as e:
        logging.error(f"Error deleting local file: {file_path} - {str(e)}")

def publish_to_start_queue(channel, message):
    try:
        queue = '03_syrin_notification_audio_process_play'
        channel.queue_declare(queue=queue, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=queue,
            body=json.dumps(message, ensure_ascii=False),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logging.info(f"Message published to queue {queue}: {message}")
    except Exception as e:
        logging.error(f"Error publishing message to queue {queue}: {str(e)}")

def publish_to_reprocess_queue(channel, message):
    try:
        # Declare the reprocessing queue with TTL and DLX
        channel.queue_declare(
            queue='02_syrin_notification_audio_reprocess_humanized',
            durable=True,
            arguments={
                'x-message-ttl': rabbitmq_ttl_dlx,  # Configurable TTL (1 minute)
                'x-dead-letter-exchange': '',  # Default DLX to route to another queue
                'x-dead-letter-routing-key': '02_syrin_notification_audio_process_humanized'  # Queue where the message will be moved
            }
        )
        # Publish the message to the reprocessing queue
        channel.basic_publish(
            exchange='',
            routing_key='02_syrin_notification_audio_reprocess_humanized',
            body=json.dumps(message, ensure_ascii=False),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        logging.info(f"Message sent to reprocessing queue: {message['humanized_text']}")
    except Exception as e:
        logging.error(f"Error sending message to reprocessing queue: {str(e)}")

def connect_to_rabbitmq():
    try:
        # Define the credentials and connection parameters
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
        
        # Set client properties, including connection name
        client_properties = {
            "connection_name": "Syrin Make Audio Agent"
        }
        
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            virtual_host=rabbitmq_vhost,
            credentials=credentials,
            client_properties=client_properties  # Pass the connection name here
        )
        
        return pika.BlockingConnection(parameters)
    except Exception as e:
        logging.error(f"Error connecting to RabbitMQ: {str(e)}")
        return None

def tts_make(txt):
    try:
        # Create the filedateprocess variable with date and time in format DD_MM_YYYY_HH_MM_SS
        filedateprocess = datetime.now().strftime('%d_%m_%Y_%H_%M_%S')

        output_path = f"/tmp/{filedateprocess}.wav"

        # Generate the audio file
        tts.tts_to_file(
            text=f'"""\n{txt}\n"""',
            speaker_wav=tts_path_clone_audio,
            language=tts_language,
            file_path=output_path,
            speed=tts_speed_voice,
            emotion=tts_emotion
        )

        return filedateprocess, output_path
    except Exception as e:
        logging.error(f"Error generating audio: {str(e)}")
        return None, None

def on_message_callback(channel, method_frame, header_frame, body):
    try:
        message = json.loads(body.decode())

        logging.info(f"Message received from queue {method_frame.routing_key}: {message['humanized_text']}, Level: {message['level']}")

        # Send the text to the tts_make function
        filedateprocess, output_path = tts_make(message['humanized_text'])

        if filedateprocess and output_path:
            # Try to upload the file to MinIO
            if upload_to_minio(output_path, f"{filedateprocess}.wav"):
                # Delete the local file after successful upload
                delete_local_file(output_path)

                # Increment the filename field
                message['filename'] = f"{filedateprocess}.wav"

                # Publish the incremented message to the process_notification_start queue
                publish_to_start_queue(channel, message)

                # Acknowledge that the message has been processed and removed from the original queue
                channel.basic_ack(method_frame.delivery_tag)
                
                logging.info(f"Audio {message['filename']} created successfully \o/")
            else:
                # Failure in uploading, send to reprocessing queue
                logging.error(f"Failed to publish generated audio. Sending to reprocessing queue.")
                publish_to_reprocess_queue(channel, message)
                channel.basic_ack(method_frame.delivery_tag)  # Acknowledge that the message has been processed
        else:
            # Failure in generating audio, send to reprocessing queue
            logging.error(f"Error processing message: {message['humanized_text']}. Audio file was not generated.")
            publish_to_reprocess_queue(channel, message)
            channel.basic_ack(method_frame.delivery_tag)  # Acknowledge that the message has been processed
    except Exception as e:
        logging.error(f"Error in callback processing message: {str(e)}")
        channel.basic_ack(method_frame.delivery_tag)

def consume_messages():
    try:
        connection = connect_to_rabbitmq()
        if connection is None:
            logging.error("Connection to RabbitMQ failed. Shutting down the application.")
            return

        channel = connection.channel()

        # Declare the queues to ensure they exist
        queues_to_declare = [
            '02_syrin_notification_audio_process_humanized',
            '02_syrin_notification_audio_reprocess_humanized',
            '03_syrin_notification_audio_process_play',
        ]

        for queue in queues_to_declare:
            channel.queue_declare(
                queue=queue, 
                durable=True,
                arguments={
                    'x-message-ttl': rabbitmq_ttl_dlx,
                    'x-dead-letter-exchange': '',
                    'x-dead-letter-routing-key': '02_syrin_notification_audio_process_humanized'
                } if queue == '02_syrin_notification_audio_reprocess_humanized' else None
            )
            logging.info(f"Queue '{queue}' checked or created.")

        # Register the callback for the queue '02_syrin_notification_audio_process_humanized'
        channel.basic_consume(queue='02_syrin_notification_audio_process_humanized', on_message_callback=on_message_callback)

        logging.info("Waiting for messages...")
        
        # Start consuming messages
        channel.start_consuming()
    except Exception as e:
        logging.error(f"Error consuming messages: {str(e)}")
    finally:
        if connection and connection.is_open:
            connection.close()
            logging.info("Connection to RabbitMQ closed.")

if __name__ == "__main__":
    try:
        logging.info("Syrin TTS Make Audio - started \o/")
        consume_messages()
    except Exception as e:
        logging.error(f"Error running the application: {str(e)}")