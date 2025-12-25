document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('download-form');
    if (!form) return;

    const logs = document.getElementById('logs');
    const progressContainer = document.getElementById('progress-container');
    const downloadButton = document.getElementById('download-button');
    const videoProgressBarsContainer = document.getElementById('video-progress-bars');

    let eventSource;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset UI
        logs.textContent = '';
        videoProgressBarsContainer.innerHTML = '';
        progressContainer.style.display = 'block';
        downloadButton.disabled = true;
        downloadButton.textContent = 'Downloading...';

        const formData = new FormData(form);

        try {
            const response = await fetch('/download', {
                method: 'POST',
                body: formData,
            });

            if (response.ok) {
                const payload = await response.json();
                const jobId = payload.job_id;
                if (!jobId) {
                    logs.textContent = 'Error: Server did not return a job id';
                    resetUI();
                    return;
                }
                // Listen for progress events
                eventSource = new EventSource(`/stream/${encodeURIComponent(jobId)}`);

                eventSource.addEventListener('message', (event) => {
                    logs.textContent += event.data + '\n';
                    logs.scrollTop = logs.scrollHeight;
                });
                
                eventSource.addEventListener('new_video', (event) => {
                    const videoTitle = event.data;
                    const progressBar = `
                        <div class="mb-2">
                            <p class="mb-0">${videoTitle}</p>
                            <div class="progress">
                                <div class="progress-bar" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
                            </div>
                        </div>
                    `;
                    videoProgressBarsContainer.innerHTML += progressBar;
                });

                eventSource.addEventListener('progress', (event) => {
                    const data = JSON.parse(event.data);
                    const lastProgressBar = videoProgressBarsContainer.lastChild.querySelector('.progress-bar');
                    if(lastProgressBar) {
                        lastProgressBar.style.width = `${data.progress}%`;
                        lastProgressBar.textContent = `${data.progress}%`;
                    }
                });

                eventSource.addEventListener('job_error', (event) => {
                    logs.textContent += `Error: ${event.data}\n`;
                    logs.scrollTop = logs.scrollHeight;
                    eventSource.close();
                    resetUI();
                });

                eventSource.addEventListener('finished', () => {
                    eventSource.close();
                    resetUI();
                });

            } else {
                const errorData = await response.json();
                logs.textContent = `Error: ${errorData.error}`;
                resetUI();
            }
        } catch (error) {
            logs.textContent = `An unexpected error occurred: ${error}`;
            resetUI();
        }
    });

    function resetUI() {
        downloadButton.disabled = false;
        downloadButton.textContent = 'Start Download';
    }
});
