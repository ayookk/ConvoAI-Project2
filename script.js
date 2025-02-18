const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const timerDisplay = document.getElementById('timer');

let mediaRecorder;
let audioChunks = [];
let timerInterval;

function formatTime(time) {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

recordButton.addEventListener('click', () => {
    // Reset audio chunks array
    audioChunks = [];
    
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.start();

            let startTime = Date.now();
            timerInterval = setInterval(() => {
                const elapsedTime = Math.floor((Date.now() - startTime) / 1000);
                timerDisplay.textContent = formatTime(elapsedTime);
            }, 1000);

            mediaRecorder.ondataavailable = e => audioChunks.push(e.data);

            mediaRecorder.onstop = () => {
                clearInterval(timerInterval);
                // Reset timer display
                timerDisplay.textContent = '00:00';
                
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const formData = new FormData();
                formData.append('audio_data', audioBlob, 'recorded_audio.wav');

                fetch('/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Upload failed');
                    }
                    window.location.reload();
                })
                .catch(error => {
                    console.error('Error uploading audio:', error);
                    alert('Failed to upload audio. Please try again.');
                });

                // Stop all tracks in the stream
                stream.getTracks().forEach(track => track.stop());
            };
        })
        .catch(error => {
            console.error('Error accessing microphone:', error);
            alert('Unable to access microphone. Please ensure microphone permissions are granted.');
            recordButton.disabled = false;
            stopButton.disabled = true;
        });

    recordButton.disabled = true;
    stopButton.disabled = false;
});

stopButton.addEventListener('click', () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    recordButton.disabled = false;
    stopButton.disabled = true;
});

// Initial button state
stopButton.disabled = true;
