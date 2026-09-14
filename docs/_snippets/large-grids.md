!!! warning "Memory for large grids"
    Readers load the whole decoded scene, volume, or field into memory before
    returning. A 0.005° MRMS grid is 98 million points and peaks near 1.2 GB;
    a GOES scene and a radar volume can expand to hundreds of megabytes. Select
    sweeps, coarser products, or shorter windows, or open `item.path` with a
    chunked backend. See [readers](/concepts/readers.md).
