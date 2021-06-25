import argparse
import asyncio
import requests
import uuid
import azure.cognitiveservices.speech as speechsdk
from azure.eventhub import EventHubProducerClient, EventData
from azure.eventhub.aio import EventHubConsumerClient


##################### ENTER YOUR VALUES HERE ######################
speechKey = ""
speechRegion = ""
translatorKey = ""
translatorEndpoint = ""
translatorRegion = ""
eventHubConnectionString = ""
eventHubName = ""

senderID = str(uuid.uuid1())

parser = argparse.ArgumentParser()
 
parser.add_argument("-l", "--language", type=str, required=True)
parser.add_argument("-hs", "--headset", action='store_true')
 
args = parser.parse_args()

language = args.language
headset = args.headset

speechConfig = speechsdk.SpeechConfig(subscription=speechKey, region=speechRegion)
speechConfig.speech_recognition_language = language
speechConfig.speech_synthesis_language = language

speechRecognizer = speechsdk.SpeechRecognizer(speech_config=speechConfig)
speechSynthesizer = speechsdk.SpeechSynthesizer(speech_config=speechConfig)

producer = EventHubProducerClient.from_connection_string(
    conn_str=eventHubConnectionString,
    eventhub_name=eventHubName
)

consumer = EventHubConsumerClient.from_connection_string(
    conn_str=eventHubConnectionString,
    consumer_group='$Default',
    eventhub_name=eventHubName,
)

def send_text(speechText):
    print("Recognized sentence:", speechText)

    eventDataBatch = producer.create_batch()

    eventData = EventData(speechText)

    eventData.properties = {'sender': senderID, 'language': language}

    eventDataBatch.add(eventData)
    producer.send_batch(eventDataBatch)
    print("Sent your sentence!")

def recognized_sentence(args):
    if args.result.text.strip():
        send_text(args.result.text)

speechRecognizer.recognized.connect(recognized_sentence)
speechRecognizer.start_continuous_recognition_async()

async def main():

    def translate(text, sourceLanguage):


        constructedUrl = translatorEndpoint + '/translate?api-version=3.0&to=' + language + '&from=' + sourceLanguage

       
        headers = {
            'Ocp-Apim-Subscription-Key': translatorKey,
            'Ocp-Apim-Subscription-Region': translatorRegion,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }

        
        body = [{
            'text' : text
        }]


        request = requests.post(constructedUrl, headers=headers, json=body)
        response = request.json()


        translated = response[0]['translations'][0]['text']

        if not headset:
            speechRecognizer.stop_continuous_recognition_async()

        speechSynthesizer.speak_text(translated)

        if not headset:
            speechRecognizer.start_continuous_recognition_async()

    async def receive_text(partitionContext, event):
        if event.properties[b'sender'].decode('ascii') == senderID:
            print("Ignoring event from self")
        else:
            receivedLanguage = event.properties[b'language'].decode('ascii')
            receivedText = event.body_as_str(encoding='UTF-8')
            print("received", receivedText, "in", receivedLanguage)
            translate(receivedText, receivedLanguage)

        await partitionContext.update_checkpoint(event)

    async def listen_for_events():
        await consumer.receive(on_event=receive_text)

    async def main_loop():
        print("Say the sentence you want to translate")

        while True:
            await asyncio.sleep(1)
           
    listeners = asyncio.gather(listen_for_events())

    await main_loop()

    listeners.cancel()

if __name__ == '__main__':
    asyncio.run(main())