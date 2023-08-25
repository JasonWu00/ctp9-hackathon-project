# ctp9-hackathon-project

This is the repository for team "If it works, it works" and their submission to the CTP Cohort 9 hackathon.

### Description of the Project

The purpose of this project is to create a Generative Adverserial Network (GAN) that takes an input image and returns an (for lack of a better word) "animefied" output image, as well as an associated front end website to allow users to make use of the GAN without having to clone this repo and run things on the command line.

### Technologies Used (placeholder)

This project makes use of the following technologies:

Front-end: React.js
Back-end: Django
Neural net models: PyTorch

### How to Use the Product

Follow the following steps to make use of our "animefier".

1. Visit [this link](http://208.167.255.60/upload).
  - The link doesn't have a unique name tied to it because the back-end is hosted out of the computer of one of the team members.
2. Select an image that you want to "animefy" (using the "Browse" button) and select one of four "animefier" styles from the drop-down menu.
3. Click the "Upload" button and wait. Since the models in question are large and the back-end doesn't have a lot of resources, it might take some time to receive your output image.
4. The website will eventually return the output image. The image will not be permanently stored on our back-end and might be deleted at any moment. Because of this, we recommend that you save the image quickly by right-clicking and selecting "Save Image As".
5. Repeat Steps 1 through 4 for as many or few images as you want.

### References

[1] Chen, Yang, Yu-Kun Lai, and Yong-Jin Liu. "CartoonGAN: Generative Adversarial Networks for Photo Cartoonization." Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition. 2018.

(Full paper: http://openaccess.thecvf.com/content_cvpr_2018/papers/Chen_CartoonGAN_Generative_Adversarial_CVPR_2018_paper.pdf)

[2]  https://github.com/znxlwm/pytorch-CartoonGAN



