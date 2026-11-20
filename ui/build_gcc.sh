set -e
apt-get update -qq >/dev/null && apt-get install -y -qq wget xz-utils libgmp-dev libmpfr-dev libmpc-dev texinfo >/dev/null 2>&1
cd /tmp && [ -f gcc-13.2.0.tar.xz ] || wget -q https://ftp.gnu.org/gcc/gcc-13.2.0/gcc-13.2.0.tar.xz || wget -q https://ftp.gnu.org/gnu/gcc/gcc-13.2.0/gcc-13.2.0.tar.xz
tar xf gcc-13.2.0.tar.xz; mkdir -p /tmp/bgcc && cd /tmp/bgcc; export PATH=/opt/nds/bin:$PATH
../gcc-13.2.0/configure --target=nds32le-elf --prefix=/out --with-as=/opt/nds/bin/nds32le-elf-as --with-ld=/opt/nds/bin/nds32le-elf-ld \
  --enable-languages=c --without-headers --with-newlib --disable-shared --disable-threads --disable-libssp --disable-nls \
  --disable-libquadmath --disable-libgomp --disable-multilib --with-arch=v3 >/tmp/cfg.log 2>&1
make -j1 all-gcc >/tmp/make.log 2>&1 && make install-gcc >>/tmp/make.log 2>&1
(make -j1 all-target-libgcc >>/tmp/make.log 2>&1 && make install-target-libgcc >>/tmp/make.log 2>&1) || echo "libgcc skipped"
cp /tmp/make.log /out/build.log; echo GCC_DONE > /out/DONE
