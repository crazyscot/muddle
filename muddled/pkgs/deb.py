"""
Some code which sneakily steals binaries from Debian/Ubuntu.

Quite a lot of code for embedded systems can be grabbed pretty much
directly from the relevant Ubuntu binary packages - this won't work
with complex packages like exim4 without some external frobulation,
since they have relatively complex postinstall steps, but it works
quite nicely for things like util-linux, and provided you're on a
supported architecture it's a quick route to externally maintained
binaries which actually work and it avoids having to build
absolutely everything in your linux yourself.

This package allows you to 'build' a package from a source file in
a checkout which is a .deb. We run dpkg with enough force options
to install it in the relevant install directory.

You still need to provide any relevant instruction files
(we'll register <filename>.instructions.xml for you automatically
if it exists).

We basically ignore the package database (there is one, but
it's always empty and stored in the object directory).
"""

import muddled.pkg as pkg
import muddled.db as db
from muddled.pkg import PackageBuilder
import muddled.utils as utils
import muddled.checkouts.simple as simple_checkouts
import os

def extract_into_obj(inv, co_name, label, pkg_file):
    co_dir = inv.checkout_path(co_name, domain = label.domain)
    obj_dir = inv.package_obj_path(label.name, label.role, domain = label.domain)
    dpkg_cmd = "dpkg-deb -X %s %s"%(os.path.join(co_dir, pkg_file), 
                                    os.path.join(obj_dir, "obj"))
    utils.run_cmd(dpkg_cmd)

    # Now install any include or lib files ..
    installed_into = os.path.join(obj_dir, "obj")
    inc_dir = os.path.join(obj_dir, "include")
    lib_dir = os.path.join(obj_dir, "lib")
    
    utils.ensure_dir(inc_dir)
    utils.ensure_dir(lib_dir)
    
    # Copy everything in usr/include ..
    src_include = os.path.join(installed_into, "usr", "include")
    src_lib = os.path.join(installed_into, "usr", "lib")
    
    if (os.path.exists(src_include) and os.path.isdir(src_include)):
        utils.copy_without(src_include,
                           inc_dir, without = None)
        
    if (os.path.exists(src_lib) and os.path.isdir(src_lib)):
        utils.copy_without(src_lib,
                           lib_dir, without = None)
    

class DebDevDependable(PackageBuilder):
    """
    Use dpkg to extract debian archives into obj/include and obj/lib
    directories so we can use them to build other packages.
    """
    def __init__(self, name, role, co, pkg_name, pkg_file, 
                 instr_name = None,
                 postInstallMakefile = None):
        """
        As for a DebDependable, really.
        """
        PackageBuilder.__init__(self, name, role)
        self.co_name = co
        self.pkg_name = pkg_name
        self.pkg_file = pkg_file
        self.instr_name = instr_name
        self.post_install_makefile = postInstallMakefile
        

    def ensure_dirs(self, builder, label):
        inv = builder.invocation

        if not os.path.exists(inv.checkout_path(self.co_name, domain = label.domain)):
            raise utils.Failure("Path for checkout %s does not exist."%self.co_name)

        utils.ensure_dir(os.path.join(inv.package_obj_path(label.name, label.role, 
                                                           domain = label.domain), "obj"))

    def build_label(self, builder, label):
        """
        Actually install the dev package.
        """
        self.ensure_dirs(builder, label)

        tag = label.tag
        
        if (tag == utils.Tags.PreConfig):
            # Nothing to do
            pass
        elif (tag == utils.Tags.Configured):
            pass
        elif (tag == utils.Tags.Built):
            pass
        elif (tag == utils.Tags.Installed):
            # Extract into /obj
            inv = builder.invocation
            extract_into_obj(inv, self.co_name, label, self.pkg_file)
        elif (tag == utils.Tags.PostInstalled):
            if self.post_install_makefile is not None:
                inv = builder.invocation
                co_path =inv.checkout_path(self.co_name, domain = label.domain) 
                os.chdir(co_path)
                utils.run_cmd("make -f %s %s-postinstall"%(self.post_install_makefile, 
                                                       label.name))
        elif (tag == utils.Tags.Clean or tag == utils.Tags.DistClean):
            # Just remove the object directory.
            inv = builder.invocation
            utils.recursively_remove(inv.package_obj_path(label.name, label.role, 
                                                          domain = label.domain))
        else:
            raise utils.Error("Invalid tag specified for deb pkg %s"%(label))



class DebDependable(PackageBuilder):
    """
    Use dpkg to extract debian archives from the given
    checkout into the install directory.
    """

    def __init__(self, name, role, co, pkg_name, pkg_file,
                 instr_name = None, 
                 postInstallMakefile = None):
        """
        * co - is the checkout name in which the package resides.
        * pkg_name - is the name of the package (dpkg needs it)
        * pkg_file - is the name of the file the package is in, relative to
          the checkout directory.
        * instr_name - is the name of the instruction file, if any.
        * postInstallMakefile - if not None::
            
            make -f postInstallMakefile <pkg-name>

          will be run at post-install time to make links, etc.
        """
        PackageBuilder.__init__(self, name, role)
        self.co_name = co
        self.pkg_name = pkg_name
        self.pkg_file = pkg_file
        self.instr_name = instr_name
        self.post_install_makefile = postInstallMakefile


    def ensure_dirs(self, builder, label):
        inv = builder.invocation

        if not os.path.exists(inv.checkout_path(self.co_name, domain = label.domain)):
            raise utils.Failure("Path for checkout %s does not exist."%self.co_name)

        utils.ensure_dir(inv.package_install_path(label.name, label.role, 
                                                  domain = label.domain))
        utils.ensure_dir(inv.package_obj_path(label.name, label.role,
                                              domain = label.domain))
        
    def build_label(self, builder, label):
        """
        Build the relevant label.
        """
        
        self.ensure_dirs(builder, label)
        
        tag = label.tag
        
        if (tag == utils.Tags.PreConfig):
            # Nothing to do.
            pass
        elif (tag == utils.Tags.Configured):
            pass
        elif (tag == utils.Tags.Built):
            pass
        elif (tag == utils.Tags.Installed):
            # Concoct a suitable dpkg command.
            inv = builder.invocation
            
            # Extract into the object directory .. so I can depend on them later.
            extract_into_obj(inv, self.co_name, label, self.pkg_file)            

            inst_dir = inv.package_install_path(label.name, label.role, 
                                                domain = label.domain)
            co_dir = inv.checkout_path(self.co_name, domain = label.domain)

            # Using dpkg doesn't work here for many reasons.
            dpkg_cmd = "dpkg-deb -X %s %s"%(os.path.join(co_dir, self.pkg_file), 
                                            inst_dir)
            utils.run_cmd(dpkg_cmd)
            
            # Pick up any instructions that got left behind
            instr_file = self.instr_name
            if (instr_file is None):
                instr_file = "%s.instructions.xml"%(label.name)
            
            instr_path = os.path.join(co_dir, instr_file)

            if (os.path.exists(instr_path)):
                # We have instructions ..
                ifile = db.InstructionFile(instr_path)
                ifile.get()
                self.builder.instruct(label.name, label.role, ifile)
        elif (tag == utils.Tags.PostInstalled):
            if self.post_install_makefile is not None:
                inv = builder.invocation
                co_path =inv.checkout_path(self.co_name, domain =  label.domain) 
                os.chdir(co_path)
                utils.run_cmd("make -f %s %s-postinstall"%(self.post_install_makefile, 
                                                           label.name))
        elif (tag == utils.Tags.Clean or tag == utils.Tags.DistClean):#
            inv = builder.invocation
            admin_dir = os.path.join(inv.package_obj_path(label.name, label.role, 
                                     domain = label.domain))
            utils.recursively_remove(admin_dir)
        else:
            raise utils.Error("Invalid tag specified for deb pkg %s"%(label))

def simple(builder, coName, name, roles, 
           depends_on = [ ],
           pkgFile = None, debName = None, instrFile = None, 
           postInstallMakefile = None, isDev = False):
    """
    Build a package called 'name' from co_name / pkg_file with
    an instruction file called instr_file. 

    'name' is the name of the muddle package and of the debian package.
    if you want them different, set deb_name to something other than
    None.
    
    Set isDev to True for a dev package, False for an ordinary
    binary package. Dev packages are installed into the object
    directory where MUDDLE_INC_DIRS etc. expects to look for them.
    Actual packages are installed into the installation directory
    where they will be transported to the target system.
    """
    if (debName is None):
        debName = name


    if (pkgFile is None):
        pkgFile = debName

    for r in roles:
        if isDev:
            dep = DebDevDependable(name, r, coName, debName, 
                                   pkgFile, instrFile, 
                                   postInstallMakefile)
        else:
            dep = DebDependable(name, r, coName, debName, 
                                pkgFile, instrFile, 
                                postInstallMakefile)
            
        pkg.add_package_rules(builder.invocation.ruleset, 
                              name, r, dep)
        # We should probably depend on the checkout .. .
        pkg.package_depends_on_checkout(builder.invocation.ruleset, 
                                        name, r, coName, dep)
        # .. and some other packages. Y'know, because we can ..
        pkg.package_depends_on_packages(builder.invocation.ruleset, 
                                        name, r, utils.Tags.PreConfig, 
                                        depends_on)
        
    # .. and that's it.

def dev(builder, coName, name, roles,
        depends_on = [ ],
        pkgFile = None, debName = None, instrFile = None,
        postInstallMakefile = None):
    """
    A wrapper for 'deb.simple', with the "idDev" flag set True.
    """
    simple(builder, coName, name, roles, depends_on,
           pkgFile, debName, instrFile, postInstallMakefile,
           isDev = True)
          

def deb_prune(h):
    """
    Given a cpiofile heirarchy, prune it so that only the useful 
    stuff is left.
    
    We do this by lopping off directories, which is easy enough in
    cpiofile heirarchies.
    """
    h.erase_target("/usr/share/doc")
    h.erase_target("/usr/share/man")



# End file.
    

        
        

