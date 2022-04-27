## Data

Create a new folder in the current directory and name it `data` , then download `Stanford3dDataset_v1.2_Aligned_Version.zip` from https://goo.gl/forms/4SoGp4KtH1jfRqEj2 and unzip it and place it under `data` , the file structure is as follows:

```bash
root
 │  .gitignore
 │  dataLoader.py
 │  dataPrepare.py
 │  main.py
 │  model.py
 │  README.md
 │  test.py
 │
 ├─data
     ├─Stanford3dDataset_v1.2_Aligned_Version
         ├─Area_1
         │    ├─ ...
         │
         ├─Area_2
         ├─ ...
```



Then switch to the current directory on the terminal and execute the `dataPrepare.py` file:

```bash
cd ./
python dataPrepare.py
```



The processed data will be placed in the `./data/s3dis_data` folder



## Train

Switch to the current directory on the terminal and execute `main.py` , and you can add the configuration items you want to add later

```bash
cd ./
python main.py
```

The configuration items are shown in the following table:

| configuration items | meaning                                        | type    |
| ------------------- | ---------------------------------------------- | ------- |
| `--save_dir`        | path to save the trained model                 | `str`   |
| `--data_path`       | dataset path, default `./data/s3dis_data`      | `str`   |
| `--batch_size`      | batch size in batch processing                 | `int`   |
| `--num_points`      | number of samples per training, default `4096` | `int`   |
| `--test_area`       | test area, default `5`                         | `int`   |
| `--block_size`      | size of sampling space, default `1`            | `float` |
| `--threads`         | number of threads during training              | `int`   |
| `--pretrain`        | whether to load the pre-trained model          | `bool`  |
| `--lr`              | learning rate, default `0.0001`                | `float` |
| `--epochs`          | training rounds                                | `int`   |
| `--model`           | model name                                     | `str`   |
| `--num_classes`     | number of semantic categories, default `13`    | `int`   |
| `--transform`       | whether data augmentation is needed            | `bool`  |
| `--gpu_id`          | which GPU you need to use                      | `int`   |



## Test

