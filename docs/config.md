## config.toml
```
# RoboSat.pink Configuration

[dataset]
  # The datasets base directory.
  path = "~/rsp_dataset"

  # Optional PostgreSQL Database connection, using psycopg2 syntax (could be use by rasterize tool).
  pg_dsn = "host=127.0.0.1 dbname=rsp user=postgres"



# Input channels configuration.
# You can, add several channels blocks to compose your input Tensor. Order is meaningful.
#
# sub:		dataset subdirectory name
# bands:	bands to keep from sub source. Order is meaningful
# mean:		bands mean value
# std:		bands std value
# Nota: (default mean and std are based on ImageNet DataSet, cf pretrained model)
[[channels]]
  sub   = "images"
  bands = [1, 2, 3]
  mean  = [0.485, 0.456, 0.406]
  std   = [0.229, 0.224, 0.225]



# Output Classes configuration.
# Nota: available colors are either CSS3 colors names or #RRGGBB hexadecimal representation.
# Nota: only support binary classification for now.
[[classes]]
  title = "background"
  color = "white"

[[classes]]
  title = "building"
  color = "deeppink"



[model]
  # Model name.
  name = "albunet"

  # Encoder model name.
  encoder = "resnet50"
  
  # Use, or not, ImageNet weights pretraining.
  pretrained = true

  # Loss function name.
  loss = "lovasz"
  
  # Batch size for training.
  # Nota: can be increase upon your available GPU RAM.
  batch_size = 2

  # tile side size in pixels.
  tile_size = 512

  # Total number of epochs to train for.
  epochs = 10

  # Learning rate for the optimizer.
  # NOTA: should be increase to ~0.0001 if you're not using pretrained models.
  lr = 0.000025

  # Data augmentation, Flip or Rotate probability.
  data_augmentation = 0.75

  # Weight decay l2 penalty for the optimizer.
  decay = 0.0
```
