
typedef struct { float r, i; } _Complex;


int main() {
    _Complex a, b, c;
    a.r = 1.0; a.i = 2.0;
    b.r = 2.0; b.i = 3.0;
    c.r = a.r + b.r;
    c.i = a.i + b.i;
    return 0;
}